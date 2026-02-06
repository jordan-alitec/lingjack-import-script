# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    date_planned_end = fields.Datetime(string='Scheduled End')
    date_finished = fields.Datetime(string='End', readonly=False)
    is_mrp_manager = fields.Boolean(
        compute="_compute_is_mrp_manager", store=False,default=True,
    )

    def _compute_is_mrp_manager(self):
        for rec in self:
          rec.is_mrp_manager = self.env.user.has_group('mrp.group_mrp_manager')
    
    @api.depends('move_raw_ids', 'move_raw_ids.product_id', 'move_raw_ids.product_id.stock_item')
    def _compute_has_non_stock_components(self):
        """Check if any components have stock_item = False"""
        for rec in self:
            rec.has_non_stock_components = any(
                move.product_id.stock_item == False 
                for move in rec.move_raw_ids 
                if move.product_id
            )

    @api.constrains('date_finished')
    def update_date_planned_end(self):
        for rec in self:
            rec.date_planned_end = rec.date_finished

    def action_start(self):
        result = super(MrpProduction, self).action_start()
        _logger.warning("action_start")
        for production in self:
            _logger.warning(production.workorder_ids.filtered(lambda w: w.state in ['pending', 'waiting']))
            production.workorder_ids.filtered(lambda w: w.state in ['pending', 'waiting']).write({'state': 'progress'})
        return result
    
    # Auto plan when confirm
    def action_confirm(self):
        confirmed_production = super(MrpProduction, self).action_confirm()

        for production in self:
            try:
                try:
                    production.button_plan()
                except:
                    pass
                if production.product_tracking not in ['none', False]:
                    production.action_generate_serial()
                
                # Auto-create pick component transfer note for two-step manufacturing
                if production.warehouse_id.manufacture_steps == 'pbm':
                    # Clean up any existing pale components first
                    production._cleanup_existing_pale_components()
                    production._auto_create_pick_component_transfer_note()
                    
            except Exception as e:
                raise UserError(f"Error while planning the production: {str(e)}")

        return confirmed_production

    def button_mark_done(self):
        """Override to check lot selection before marking done"""
        self.ensure_one()
        
        # Check for components requiring manual lot selection
        components_needing_lots = []
        for move in self.move_raw_ids:
            if (move.product_id.tracking in ['lot', 'serial'] and 
                move.product_id.manual_lot_reservation and
                not move.lot_ids):
                components_needing_lots.append(move)
        
        # If components need manual lot selection, create and show wizard
        if components_needing_lots:
            # Create the wizard record
            wizard = self.env['lot.selection.wizard'].create({
                'production_id': self.id,
            })
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Lot Selection Required'),
                'res_model': 'lot.selection.wizard',
                'views': [[self.env.ref('lingjack_shop_floor.view_lot_selection_wizard_form').id, 'form']],
                'res_id': wizard.id,
                'view_mode': 'form',
                'target': 'new',
            }
        
        # Auto-assign lots for components that don't require manual selection
        self._auto_assign_lots()

        # Auto assign according to bom if nothing is assigned
        for move in self.move_raw_ids:
            # if nothing is assigned only we assign according to bom
            if move.quantity == 0 and not move.picked:
                move.write({'quantity': move.product_uom_qty})
   
        # Customer don`t want to let the operator bother ab outh this, they will unlock and edit afterward
        self.move_raw_ids.write({'picked':True})
        result = super().button_mark_done()
        return result

    def _auto_assign_lots(self):
        """Auto-assign lots for components that don't require manual selection"""
        for move in self.move_raw_ids:
            '''
            This is because default odoo will be using stock quant without lot by defualt
            '''
            if move.product_id.tracking == 'none' and move.product_id.manual_lot_reservation:
                continue

            move._do_unreserve()
            move.picked = False
            move._action_assign()
            move.picked = True



    # Pick Component
    is_rework = fields.Boolean(
        string='Modification Order',
        help='Indicates if this production order is a rework.'
    )
    
    has_non_stock_components = fields.Boolean(
        string='Has Non-Stock CompFvonents',
        compute='_compute_has_non_stock_components',
        store=False,
        help='True if any components have stock_item = False'
    )

    @api.onchange('qty_producing')
    @api.constrains('qty_producing')
    def onchange_check_manual_producing(self):

        for rec in self:

            if rec.workorder_ids and rec.qty_producing > self._get_qty_produced() and rec.qty_producing != 0:
                rec.qty_producing = self._get_qty_produced()
                # raise ValidationError(f"The qualified quantity in the work order should always be greater than the quantity producing.")

    def _get_qty_produced(self):
        if self.workorder_ids:

            return min(self.workorder_ids.filtered(lambda m: 'Quality' not in m.name).mapped('qty_produced'))
        else:
            return 0

    def _compute_qualified_quantities(self):
        for rec in self:
            if rec.state != 'draft':
                rec.qty_producing = rec._get_qty_produced()
                rec._set_qty_producing()

    def recalculate_source_requested_qty(self):
        for move in self.move_raw_ids:
            move._compute_source_requested_qty()

    def _set_qty_producing(self, pick_manual_consumption_moves=True):

        if self.qty_producing == 0:
            return


        for move in (
            self.move_raw_ids.filtered(lambda m: not self.warehouse_id.manufacture_steps != 'mrp_one_step'
                                          or m.product_id.tracking == 'none')
            | self.move_finished_ids.filtered(lambda m: m.product_id != self.product_id or m.product_id.tracking == 'serial')
        ):
            move.picked = False
        # Call the original _set_qty_producing method (super)
        super(MrpProduction, self)._set_qty_producing(pick_manual_consumption_moves)

        self.action_assign()
        # Now loop over all moves and set move.picked to False
        for move in (
            self.move_raw_ids.filtered(lambda m: not self.warehouse_id.manufacture_steps != 'mrp_one_step'
                                          or m.product_id.tracking == 'none')
            | self.move_finished_ids.filtered(lambda m: m.product_id != self.product_id or m.product_id.tracking == 'serial')
        ):

            move.picked = False


    def action_pick_component(self):
        """Pick/consume components for this production order"""
        # Clean up any existing pale components from transfer notes
        self._cleanup_existing_pale_components()
        
        # Check if there are components to consume
        if not self.move_raw_ids:
            raise UserError(_('No components to pick for this production order.'))

        # Get ALL components for this production, excluding pale components
        # This allows users to see everything and remove what they don't need
        all_moves = self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and 
                     m.product_uom_qty > 0 and 
                     not m.product_id.take_in_pale
        )

        if not all_moves:
            # Check if there are pale components that were excluded
            pale_moves = self.move_raw_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and 
                         m.product_uom_qty > 0 and 
                         m.product_id.take_in_pale
            )
            if pale_moves:
                pale_names = ', '.join(pale_moves.mapped('product_id.name'))
                raise UserError(_('No components found for this production order. Note: Components marked as "Take in Pale" (%s) are automatically excluded from pick component process.') % pale_names)
            else:
                raise UserError(_('No components found for this production order.'))

        # Create component line values for the picker wizard
        component_line_vals = []
        for component in all_moves:
            # Calculate remaining quantity (total required - already consumed)
            remaining_qty = component.product_uom_qty - component.actual_requested_qty

            # Only add components that still have remaining quantity to pick
            if remaining_qty > 0 and component.product_id.is_storable:
                line_vals = {
                    'product_id': component.product_id.id,
                    # 'workorder_id': component.workorder_id.id if component.workorder_id else False,
                    'available_quantity': component.product_id.qty_available + 10,
                    'forecast_quantity': component.forecast_qty,
                    'quantity_required': remaining_qty,
                    'quantity_to_pick': 0,  # Use remaining quantity instead of full quantity
                    'uom_id': component.product_uom.id,
                    'move_raw_id': component.id,
                }

                component_line_vals.append((0, 0, line_vals))
            component._compute_source_requested_qty()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pick Components: %s') % self.name,
            'res_model': 'shop.floor.production.component.picker',
            'view_mode': 'form',
            'target': 'new',
            'views': [[False, 'form']],
            'context': {
                'default_production_id': self.id,
                'default_component_line_ids': component_line_vals,
            }
        }

    def action_open_work_orders(self):
        """ Method to open the Gantt view of Work orders related to the current MO """
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.action_mrp_workorder_workcenter")
        action.update({
            'view_mode': 'gantt',
            'domain': [('id', 'in', self.workorder_ids.ids)]
            })
        return action

    def action_open_time_tracking_gantt(self):
        """ Method to open the Gantt view of productivity records (time tracking) related to the current MO """
        # Get all productivity records from all work orders of this MO
        productivity_ids = self.workorder_ids.mapped('time_ids').ids

        action = {
            'name': f'Time Tracking - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'gantt,list,form',
            'views': [
                (self.env.ref('lingjack_shop_floor.view_mrp_workcenter_productivity_gantt_time_tracking').id, 'gantt'),
                (False, 'list'),
                (False, 'form')
            ],
            'domain': [('id', 'in', productivity_ids)],
            'context': {
                'default_workorder_id': self.workorder_ids[0].id if self.workorder_ids else False,
                'group_by': 'workorder_id',
                'search_default_group_by_workorder': 1,
                'search_default_include_workorders_without_tracking': 1,
            },
            'target': 'current',
            'help': _("""
                <p class="o_view_nocontent_smiling_face">
                    No time tracking records found
                </p>
                <p>
                    This view shows time tracking sessions for work orders.
                    Work orders without time tracking are also displayed in blue.
                </p>
            """),
        }
        return action

    def _auto_create_pick_component_transfer_note(self):
        """Auto-create pick component transfer note for two-step manufacturing"""
        self.ensure_one()
        
        warehouse = self.picking_type_id.warehouse_id
        if not warehouse or not warehouse.pbm_type_id:
            _logger.warning(f"No Pick Components operation type (pbm_type_id) configured for warehouse {warehouse.name if warehouse else 'None'}")
            return

        # Check if pick component transfer note already exists
        existing_picking = self.picking_ids.filtered(
            lambda p: p.picking_type_id.id == warehouse.pbm_type_id.id and p.state not in ('done', 'cancel')
        )
        
        if existing_picking:
            # Clean up any pale components and update existing picking state
            existing_picking[0]._remove_pale_components()
            existing_picking[0]._update_pick_component_state()
            return existing_picking[0]

        # Create new pick component transfer note
        picking_vals = {
            'picking_type_id': warehouse.pbm_type_id.id,
            'location_id': warehouse.pbm_type_id.default_location_src_id.id,
            'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
            'origin': f'{self.name} (Pick Components)',
            'partner_id': False,
            'move_type': 'direct',
            'state': 'waiting',  # Default state when nothing is requested
            'group_id': self.procurement_group_id.id if self.procurement_group_id else False,
            'mrp_production_id': self.id,  # Link to MO
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Check for pale components that will be excluded
        pale_components = self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and 
                     m.product_uom_qty > 0 and 
                     m.product_id.take_in_pale
        )
        if pale_components:
            pale_names = ', '.join(pale_components.mapped('product_id.name'))
            _logger.info(f"Excluding pale components from pick component transfer note {picking.name}: {pale_names}")
        
        # Create moves for all components that need to be picked, excluding pale components
        for move_raw in self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and 
                     m.product_uom_qty > 0 and 
                     m.product_id.is_storable and
                     not m.product_id.is_setsco_label and
                     not m.product_id.take_in_pale
        ):
            move_vals = {
                'name': f"Pick {move_raw.product_id.display_name} for {self.name}",
                'product_id': move_raw.product_id.id,
                'product_uom_qty': 0,  # Start with 0, will be updated when requested
                'product_uom': move_raw.product_uom.id,
                'picking_id': picking.id,
                'location_id': warehouse.pbm_type_id.default_location_src_id.id,
                'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
                'origin': self.name,
                'reference': self.name,
                'group_id': self.procurement_group_id.id if self.procurement_group_id else False,
                'state': 'draft',
                'workorder_id': move_raw.workorder_id.id if move_raw.workorder_id else False,
                'quantity_requested': 0,  # No quantity requested initially
                'move_raw_id': move_raw.id,  # Link to original raw material move
            }
            self.env['stock.move'].create(move_vals)
        
        # Set initial state to 'waiting' since no quantities are requested yet
        picking.state = 'waiting'
        
        _logger.info(f"Auto-created pick component transfer note {picking.name} for MO {self.name}")
        return picking

    def _cleanup_existing_pale_components(self):
        """Clean up any pale components from existing pick component transfer notes"""
        self.ensure_one()
        
        warehouse = self.picking_type_id.warehouse_id
        if not warehouse or not warehouse.pbm_type_id:
            return
        
        # Find existing pick component transfer notes
        existing_pickings = self.picking_ids.filtered(
            lambda p: p.picking_type_id.id == warehouse.pbm_type_id.id and p.state not in ('done', 'cancel')
        )
        
        for picking in existing_pickings:
            picking._remove_pale_components()
    
    def action_create_purchase_request(self):
        """Create purchase request for non-stock components"""
        self.ensure_one()
        
        # Get non-stock components
        non_stock_moves = self.move_raw_ids.filtered(
            lambda m: m.product_id and m.product_id.stock_item == False
        )
        
        if not non_stock_moves:
            raise UserError(_('No non-stock components found for this manufacturing order.'))
        
        # Prepare component data for wizard
        component_lines = []
        for move in non_stock_moves:
            component_lines.append((0, 0, {
                'product_id': move.product_id.id,
                'product_qty': move.product_uom_qty,
                'product_uom_id': move.product_uom.id,
                'move_raw_id': move.id,
            }))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Purchase Request for Non-Stock Components'),
            'res_model': 'mrp.purchase.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_component_line_ids': component_lines,
            }
        }