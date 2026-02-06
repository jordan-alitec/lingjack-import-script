# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShopFloorProductionComponentPicker(models.TransientModel):
    _name = 'shop.floor.production.component.picker'
    _description = 'Shop Floor Production Component Picker'

    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',
        required=True,
        readonly=True
    )
    
    move_ids = fields.Many2many(
        'stock.move',
        string='Available Components',
        readonly=True
    )
    
    component_line_ids = fields.One2many(
        'shop.floor.production.component.line',
        'picker_id',
        string='Components to Pick'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if 'production_id' in self.env.context:
            production_id = self.env.context['production_id']
            production = self.env['mrp.production'].browse(production_id)
            
            # Get components for this production
            component_moves = production.move_raw_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty > 0
            )
            
            if component_moves:
                res['move_ids'] = [(6, 0, component_moves.ids)]
                
                # Create lines for each component
                line_vals = []
                for move in component_moves:
                    # Calculate remaining quantity (total required - already consumed)
                    remaining_qty = move.product_uom_qty - move.quantity
                    
                    # Only add components that still have remaining quantity to pick
                    if remaining_qty > 0:
                        line_vals.append((0, 0, {
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'workorder_id': move.workorder_id.id if move.workorder_id else False,
                                'available_quantity': move.product_id.qty_available,
                                'quantity_to_pick': remaining_qty,  # Use remaining quantity instead of full quantity
                            'uom_id': move.product_uom.id,
                        }))
                res['component_line_ids'] = line_vals
        
        return res

    def action_pick_components(self):
        """Execute the component picking by creating a stock picking"""
        self.ensure_one()

        # Validate that at least one component has quantity > 0
        lines_to_pick = self.component_line_ids.filtered(lambda l: l.quantity_to_pick > 0)
        if not lines_to_pick:
            raise UserError(_('Please specify quantity to pick for at least one component.'))

        # Get warehouse and operation type
        warehouse = self.production_id.picking_type_id.warehouse_id
        if not warehouse:
            raise UserError(_('No warehouse found for this work order.'))

        if not warehouse.pbm_type_id:
            raise UserError(
                _('No Pick Components operation type (pbm_type_id) configured for warehouse %s.') % warehouse.name)

        # Create stock picking
        picking_vals = {
            'picking_type_id': warehouse.pbm_type_id.id,
            'location_id': warehouse.pbm_type_id.default_location_src_id.id,
            'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
            'origin': self.production_id.name,
            'partner_id': False,  # Internal transfer
            'move_type': 'direct',  # All at once
            'state': 'draft',
            'group_id': self.production_id.procurement_group_id.id
        }


        picking = self.env['stock.picking'].create(picking_vals)
        _logger.info(f"[Shop Floor] Created stock picking {picking.name} for production {self.production_id.name}")


        # Set the production reference on the picking for traceability
        picking.write({
            'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
        })

        # Create stock moves for each component line
        move_vals_list = []
        for line in lines_to_pick:
            # Get source move for reference - find the original move from production
            source_move = self.production_id.move_raw_ids.filtered(
                lambda m: m.product_id.id == line.product_id.id and 
                         (not line.workorder_id or m.workorder_id.id == line.workorder_id.id)
            )[:1]  # Take the first match

            move_vals = {
                'name': f"Pick {line.product_id.name} for {self.production_id.name}",
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity_to_pick,
                'product_uom': line.uom_id.id,
                'picking_id': picking.id,
                'location_id': warehouse.pbm_type_id.default_location_src_id.id,
                'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
                'origin': self.production_id.name,
                'reference': source_move.reference if source_move else self.production_id.name,
                'workorder_id': line.workorder_id.id if line.workorder_id else False,
                'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
                'state': 'draft',
            }
            move_vals_list.append(move_vals)

        # Create all moves
        moves = self.env['stock.move'].create(move_vals_list)
        _logger.info(f"[Shop Floor] Created {len(moves)} stock moves for picking {picking.name}")

        # Confirm the picking to make it ready
        try:
            picking.action_confirm()
            _logger.info(f"[Shop Floor] Confirmed picking {picking.name}")

            # Optionally assign if there's enough stock
            picking.action_assign()

            picking_state = dict(picking._fields['state'].selection).get(picking.state, picking.state)
            message = _(
                'Stock picking %s has been created and is %s. You can process it from the Inventory module.') % (
                          picking.name, picking_state.lower() if picking_state else 'unknown'
                      )

        except Exception as e:
            _logger.warning(f"[Shop Floor] Could not confirm picking {picking.name}: {e}")
            message = _(
                'Stock picking %s has been created but needs manual confirmation. Please check the Inventory module.') % picking.name

        # Send notifications to configured users
        self._send_component_pick_notifications(picking, lines_to_pick)

        # Return action to view the created picking
        return {
            'type': 'ir.actions.act_window',
            'name': _('Component Picking Created'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_picking_type_id': warehouse.pbm_type_id.id,
            }
        }

    def _send_component_pick_notifications(self, picking, component_lines):
        """Send notifications to configured users about component picking creation"""
        # Get configured users from company settings
        company = self.env.company
        users_to_notify = company.shop_floor_component_pick_notify_user_ids
        
        if not users_to_notify:
            _logger.info("[Shop Floor] No users configured for component pick notifications in company %s", company.name)
            return

        try:
            # Prepare notification message
            component_names = ', '.join(component_lines.mapped('product_id.name'))
            total_components = len(component_lines)
            
            notification_title = _('Component Picking Created')
            notification_body = _(
                'Component picking %(picking_name)s has been created for manufacturing order %(mo_name)s.\n\n'
                'Components (%(total)d items):\n%(components)s\n\n'
                'Please process this picking in the Inventory module.'
            ) % {
                'picking_name': picking.name,
                'mo_name': self.production_id.name,
                'total': total_components,
                'components': component_names
            }

            # Send notification to each configured user
            for user in users_to_notify:
                if user.active:  # Only notify active users
                    self.env['mail.message'].create({
                        'subject': notification_title,
                        'body': notification_body,
                        'model': 'stock.picking',
                        'res_id': picking.id,
                        'message_type': 'notification',
                        'partner_ids': [(4, user.partner_id.id)] if user.partner_id else [],
                        'notification_ids': [(0, 0, {
                            'res_partner_id': user.partner_id.id,
                            'notification_type': 'inbox',
                            'is_read': False,
                        })] if user.partner_id else [],
                    })

            _logger.info(f"[Shop Floor] Sent component pick notifications to {len(users_to_notify)} users for picking {picking.name}")

        except Exception as e:
            _logger.error(f"[Shop Floor] Error sending component pick notifications: {e}")
            # Don't fail the picking creation if notification fails



class ShopFloorProductionComponentLine(models.TransientModel):
    _name = 'shop.floor.production.component.line'
    _description = 'Shop Floor Production Component Line'

    picker_id = fields.Many2one(
        'shop.floor.production.component.picker',
        string='Picker',
        required=True,
        ondelete='cascade'
    )
    
    move_id = fields.Many2one(
        'stock.move',
        string='Source Stock Move',
        readonly=True,
        help='Original stock move from production for reference'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True
    )
    
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        readonly=False,
        help='Work order that uses this component'
    )
    
    quantity_to_pick = fields.Float(
        string='Quantity to Pick',
        required=True
    )
    
    available_quantity = fields.Float(
        string='Available Quantity',
        readonly=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        readonly=False
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-select UoM when product is selected"""
        if self.product_id:
            # Set the UoM to the product's default UoM
            self.uom_id = self.product_id.uom_id.id
            self.available_quantity = self.product_id.qty_available
        else:
            # Clear UoM if no product is selected
            self.available_quantity = 0
            self.uom_id = False

    @api.constrains('quantity_to_pick', 'available_quantity')
    def _check_quantity_to_pick(self):
        for line in self:
            if line.quantity_to_pick < 0:
                raise ValidationError(_('Quantity to pick cannot be negative.'))



class ShopFloorProductionFinishPicker(models.TransientModel):
    _name = 'shop.floor.production.finish.picker'
    _description = 'Shop Floor Production Finish Product Picker'

    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',
        required=True,
        readonly=True
    )
    
    move_ids = fields.Many2many(
        'stock.move',
        string='Available Finished Products',
        readonly=True
    )
    
    finish_line_ids = fields.One2many(
        'shop.floor.production.finish.line',
        'picker_id',
        string='Finished Products to Pick'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # If finish_line_ids are already provided in context (from action_pick_finish_component),
        # use those instead of calculating them here
        if 'default_finish_line_ids' in self.env.context:
            res['finish_line_ids'] = self.env.context['default_finish_line_ids']
            return res
        
        if 'production_id' in self.env.context:
            production_id = self.env.context['production_id']
            production = self.env['mrp.production'].browse(production_id)
            
            # Check if there's a main product to produce
            if not production.product_id:
                return res
            
            # Calculate the quantity that can be picked based on what's been produced
            available_qty = production.total_shop_floor_qty or 0.0
            already_sent = production.qty_sent_to_warehouse or 0.0
            remaining_qty = available_qty - already_sent
            
            # Only create lines if there's something to pick
            if remaining_qty > 0:
                line_vals = [(0, 0, {
                    'product_id': production.product_id.id,
                    'workorder_id': False,  # Main product doesn't have a specific workorder
                    'available_quantity': remaining_qty,
                    'quantity_to_pick': remaining_qty,  # Default to all remaining quantity
                    'uom_id': production.product_uom_id.id,
                })]
                res['finish_line_ids'] = line_vals
        
        return res

    def action_pick_finished_products(self):
        """Execute the finished product picking by creating a stock picking"""
        self.ensure_one()
        
        # Validate that at least one product has quantity > 0
        lines_to_pick = self.finish_line_ids.filtered(lambda l: l.quantity_to_pick > 0)
        if not lines_to_pick:
            raise UserError(_('Please specify quantity to pick for at least one finished product.'))

        # Get warehouse and operation type
        warehouse = self.production_id.picking_type_id.warehouse_id
        if not warehouse:
            raise UserError(_('No warehouse found for this production order.'))

        # Use the production's picking type for finished products
        picking_type = self.production_id.picking_type_id
        if not picking_type:
            raise UserError(_('No picking operation type found for this production order.'))

        # Create stock picking for finished products
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'origin': self.production_id.name,
            'partner_id': False,  # Internal transfer
            'move_type': 'direct',  # All at once
            'state': 'draft',
            'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
            'production_id': self.production_id.id,  # Link to production order
        }

        picking = self.env['stock.picking'].create(picking_vals)
        _logger.info(f"[Shop Floor] Created finished product picking {picking.name} for production {self.production_id.name}")

        # Create stock moves for each finished product line
        move_vals_list = []
        for line in lines_to_pick:
            # For the main product, we don't need to find a source move
            # Just create the move directly
            move_vals = {
                'name': f"Pick finished {line.product_id.name} from {self.production_id.name}",
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity_to_pick,
                'product_uom': line.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'origin': self.production_id.name,
                'reference': self.production_id.name,
                'workorder_id': line.workorder_id.id if line.workorder_id else False,
                'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
                'state': 'draft',
            }
            move_vals_list.append(move_vals)

        # Create all moves
        moves = self.env['stock.move'].create(move_vals_list)
        _logger.info(f"[Shop Floor] Created {len(moves)} stock moves for finished product picking {picking.name}")

        # Confirm the picking to make it ready
        try:
            picking.action_confirm()
            _logger.info(f"[Shop Floor] Confirmed finished product picking {picking.name}")

            # Optionally assign if there's enough stock
            picking.action_assign()

            picking_state = dict(picking._fields['state'].selection).get(picking.state, picking.state)
            message = _(
                'Finished product picking %s has been created and is %s. You can process it from the Inventory module.') % (
                          picking.name, picking_state.lower() if picking_state else 'unknown'
                      )

        except Exception as e:
            _logger.warning(f"[Shop Floor] Could not confirm finished product picking {picking.name}: {e}")
            message = _(
                'Finished product picking %s has been created but needs manual confirmation. Please check the Inventory module.') % picking.name

        # Return action to view the created picking
        return {
            'type': 'ir.actions.act_window',
            'name': _('Finished Product Picking Created'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_picking_type_id': picking_type.id,
            }
        }


class ShopFloorProductionFinishLine(models.TransientModel):
    _name = 'shop.floor.production.finish.line'
    _description = 'Shop Floor Production Finish Product Line'

    picker_id = fields.Many2one(
        'shop.floor.production.finish.picker',
        string='Picker',
        required=True,
        ondelete='cascade'
    )
    
    move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        readonly=True,
        help='Original stock move from production for reference (optional)'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True
    )
    
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        readonly=True,
        help='Work order that produces this product'
    )
    
    quantity_to_pick = fields.Float(
        string='Quantity to Pick',
        required=True
    )
    
    available_quantity = fields.Float(
        string='Available Quantity',
        readonly=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        readonly=True
    )

    @api.constrains('quantity_to_pick', 'available_quantity')
    def _check_quantity_to_pick(self):
        for line in self:
            if line.quantity_to_pick < 0:
                raise ValidationError(_('Quantity to pick cannot be negative.'))
            _logger.warning('line.quantity_to_pick')
            _logger.warning(line.quantity_to_pick)
            _logger.warning('line.available_quantity')
            _logger.warning(line.available_quantity)
            _logger.warning(line.product_id)
            if line.quantity_to_pick > line.available_quantity:
                raise ValidationError(_('Cannot pick more than available quantity for %s.') % line.product_id.name) 