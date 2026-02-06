# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShopFloorComponentPicker(models.TransientModel):
    _name = 'shop.floor.component.picker'
    _description = 'Shop Floor Component Picker'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        required=True,
        readonly=True
    )

    
    component_line_ids = fields.One2many(
        'shop.floor.component.line',
        'picker_id',
        string='Components to Pick'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if 'workorder_id' in self.env.context:
            workorder_id = self.env.context['workorder_id']
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            
            # Get components for this work order
            component_moves = workorder.move_raw_ids.filtered(
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
                            'available_quantity': remaining_qty,  # Show remaining quantity as available
                            'quantity_to_pick': remaining_qty,  # Default to remaining quantity
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
        warehouse = self.workorder_id.production_id.picking_type_id.warehouse_id
        if not warehouse:
            raise UserError(_('No warehouse found for this work order.'))
        
        if not warehouse.pbm_type_id:
            raise UserError(_('No Pick Components operation type (pbm_type_id) configured for warehouse %s.') % warehouse.name)
        
        # Create stock picking
        picking_vals = {
            'picking_type_id': warehouse.pbm_type_id.id,
            'location_id': warehouse.pbm_type_id.default_location_src_id.id,
            'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
            'origin': self.workorder_id.production_id.name,
            'partner_id': False,  # Internal transfer
            'move_type': 'direct',  # All at once
            'state': 'draft',
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        _logger.info(f"[Shop Floor] Created stock picking {picking.name} for workorder {self.workorder_id.name}")
        
        # Create stock moves for each component line
        move_vals_list = []
        for line in lines_to_pick:
            # Get source move for reference
            source_move = line.move_id
            
            move_vals = {
                'name': f"Pick {line.product_id.name} for {self.workorder_id.name}",
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity_to_pick,
                'product_uom': line.uom_id.id,
                'picking_id': picking.id,
                'location_id': warehouse.pbm_type_id.default_location_src_id.id,
                'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
                'origin': self.workorder_id.production_id.name,
                'reference': source_move.reference if source_move else '',
                'raw_material_production_id': self.workorder_id.production_id.id,
                'workorder_id': self.workorder_id.id,
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
            message = _('Stock picking %s has been created and is %s. You can process it from the Inventory module.') % (
                picking.name, picking_state.lower() if picking_state else 'unknown'
            )
            
        except Exception as e:
            _logger.warning(f"[Shop Floor] Could not confirm picking {picking.name}: {e}")
            message = _('Stock picking %s has been created but needs manual confirmation. Please check the Inventory module.') % picking.name
        
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


class ShopFloorComponentLine(models.TransientModel):
    _name = 'shop.floor.component.line'
    _description = 'Shop Floor Component Line'

    picker_id = fields.Many2one(
        'shop.floor.component.picker',
        string='Picker',
        required=True,
        ondelete='cascade'
    )
    
    move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        required=True,
        readonly=True
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=False
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
            # if line.quantity_to_pick > line.available_quantity:
            #     raise ValidationError(_('Cannot pick more than available quantity for %s.') % line.product_id.name)