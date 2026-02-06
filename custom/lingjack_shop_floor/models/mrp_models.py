# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    quantity_produced = fields.Float(
        string='Quantity Produced',
        help='Quantity produced during this productivity period'
    )
    
    defect_quantity = fields.Float(
        string='Defect Quantity',
        help='Quantity that failed quality check'
    )
    
    notes = fields.Text(string='Production Notes')

    def action_add_quantity_popup(self):
        """Open popup to add quantity produced"""
        if self.date_end:
            raise UserError(_('Cannot add quantity to a completed productivity record.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Quantity Produced'),
            'res_model': 'shop.floor.quantity.popup',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_productivity_id': self.id,
                'default_workorder_id': self.workorder_id.id,
                'default_employee_id': self.user_id.employee_id.id if self.user_id.employee_id else False,
            }
        }

    def write(self, vals):
        """Override to update workorder quantities when productivity changes"""
        res = super().write(vals)
        
        # If any quantity-related fields are updated, trigger workorder recomputation
        if any(field in vals for field in ['quantity_produced', 'defect_quantity']):
            workorders_to_update = self.env['mrp.workorder']
            for record in self:
                if record.workorder_id:
                    workorders_to_update |= record.workorder_id
            
            # Force recomputation of workorder totals for all affected workorders
            if workorders_to_update:
                workorders_to_update._compute_total_quantity_produced()
                _logger.info(f"[Shop Floor] Updated {len(vals)} fields, recomputed totals for workorders: {workorders_to_update.mapped('name')}")
        
        return res


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    total_quantity_produced = fields.Float(
        string='Total Quantity Produced',
        compute='_compute_total_quantity_produced',
        store=True,
        help='Total quantity produced from all productivity records'
    )
    
    total_defect_quantity = fields.Float(
        string='Total Defect Quantity',
        compute='_compute_total_quantity_produced',
        store=True,
        help='Total defect quantity from all productivity records'
    )
    
    production_efficiency = fields.Float(
        string='Production Efficiency %',
        compute='_compute_production_efficiency',
        help='(Good Quantity / Total Quantity) * 100'
    )

    @api.depends('time_ids.quantity_produced', 'time_ids.defect_quantity')
    def _compute_total_quantity_produced(self):
        for workorder in self:
            # Get all productivity records for this workorder
            productivity_records = workorder.time_ids
            quantities = productivity_records.mapped('quantity_produced')
            defects = productivity_records.mapped('defect_quantity')
            
            # Sum all quantities from all sessions
            total_quantity_produced = sum(quantities) if quantities else 0.0
            workorder.qty_produced = total_quantity_produced
            workorder.total_quantity_produced = total_quantity_produced
            workorder.total_defect_quantity = sum(defects) if defects else 0.0
            
            # Debug logging to verify computation
            if quantities:
                _logger.info(f"[Shop Floor] Workorder {workorder.name}: {len(productivity_records)} sessions, "
                           f"quantities: {quantities}, total: {workorder.total_quantity_produced}")

    @api.depends('total_quantity_produced', 'total_defect_quantity')
    def _compute_production_efficiency(self):
        for workorder in self:
            if workorder.total_quantity_produced > 0:
                good_qty = workorder.total_quantity_produced - workorder.total_defect_quantity
                workorder.production_efficiency = (good_qty / workorder.total_quantity_produced) * 100
            else:
                workorder.production_efficiency = 0.0

    def button_start(self):
        """Override start button to show popup, but handle differently from shop floor"""
        # Check if this is from shop floor display (MRP display interface)
        # In shop floor display, we don't want popup on start, only on stop
        if self.env.context.get('mrp_display') or self.env.context.get('shop_floor_mode'):
            # Shop floor mode - just start normally without popup
            return super().button_start()
        
        # Regular workorder form - start session and show popup immediately
        res = super().button_start()
        
        # Get the newly created productivity record
        active_productivity = self.time_ids.filtered(lambda p: not p.date_end)
        
        if active_productivity:
            # Show popup for regular interface
            return {
                'type': 'ir.actions.act_window',
                'name': _('Log Session Quantity'),
                'res_model': 'shop.floor.quantity.popup',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_productivity_id': active_productivity[0].id,
                    'default_workorder_id': self.id,
                    'default_employee_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
                    'close_session_after_save': True,
                    'from_start_button': True,  # Flag to indicate this came from start button
                }
            }
        
        return res

    def button_finish(self):
        """Override finish button to show quantity popup for session stop"""
        # Get active productivity record
        active_productivity = self.time_ids.filtered(lambda p: not p.date_end)
        
        if active_productivity:
            # Always show popup to log quantity for this session before stopping
            return {
                'type': 'ir.actions.act_window',
                'name': _('Log Session Quantity'),
                'res_model': 'shop.floor.quantity.popup',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_productivity_id': active_productivity[0].id,
                    'default_workorder_id': self.id,
                    'default_employee_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
                    'close_session_after_save': True,  # Flag to close session after saving quantity
                }
            }
        
        # If no active session, just finish normally
        return super().button_finish()

    def button_pending(self):
        """Override pending button to show quantity popup for session pause"""
        # Check if this is called from popup to avoid infinite loop
        _logger.warning('skip')
        _logger.warning(self.env.context.get('skip_popup'))
        if self.env.context.get('skip_popup'):
            return super().button_pending()
        
        # Get active productivity record
        active_productivity = self.time_ids.filtered(lambda p: not p.date_end)
        
        if active_productivity:
            # Always show popup to log quantity for this session before pausing
            return {
                'type': 'ir.actions.act_window',
                'name': _('Log Session Quantity'),
                'res_model': 'shop.floor.quantity.popup',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_productivity_id': active_productivity[0].id,
                    'default_workorder_id': self.id,
                    'default_employee_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
                    'default_continue_to_pending': True,  # Set the field default
                    'close_session_after_save': True,  # Flag to close session after saving quantity
                    'continue_to_pending': True,  # Flag to indicate this will go to pending state
                }
            }
        
        # If no active session, just go to pending normally
        return super().button_pending()

    def action_view_productivity_with_quantity(self):
        """View productivity records with quantity information"""
        action = self.env.ref('mrp.action_mrp_workcenter_productivity_report').read()[0]
        action['domain'] = [('workorder_id', '=', self.id)]
        action['context'] = {'default_workorder_id': self.id}
        action['name'] = _('Productivity - %s') % self.name
        return action

    def debug_quantity_calculation(self):
        """Debug method to check quantity calculations"""
        productivity_records = self.time_ids
        quantities = productivity_records.mapped('quantity_produced')
        defects = productivity_records.mapped('defect_quantity')
        
        debug_info = {
            'workorder': self.name,
            'total_sessions': len(productivity_records),
            'session_quantities': quantities,
            'session_defects': defects,
            'computed_total': sum(quantities),
            'computed_defects': sum(defects),
            'current_total_quantity_produced': self.total_quantity_produced,
            'current_total_defect_quantity': self.total_defect_quantity,
        }
        
        _logger.info(f"[Shop Floor Debug] {debug_info}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug Information'),
                'message': f'Check server logs for detailed debug info for {self.name}',
                'type': 'info',
                'sticky': True,
            }
        }

    def action_pick_component(self):
        """Pick/consume components for this work order"""
        # Check if there are components to consume
        if not self.move_raw_ids:
            raise UserError(_('No components to pick for this work order.'))
        
        # Check if any components are available
        available_moves = self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty > 0
        )
        
        if not available_moves:
            raise UserError(_('No components found for this work order.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pick Components: %s') % self.name,
            'res_model': 'shop.floor.component.picker.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
            }
        }

    def action_pick_finish_component(self):
        """Pick/produce finished components for this work order"""
        # Check if there are finished products to produce
        if not self.move_finished_ids:
            raise UserError(_('No finished products to pick for this work order.'))
        
        # Get ALL finished moves (users can remove what they don't need)
        # But consider actual producible quantities based on components and work done
        all_moves = self.move_finished_ids.filtered(
            lambda m: m.state in ('assigned', 'waiting', 'confirmed') and m.product_uom_qty > 0
        )
        
        if not all_moves:
            raise UserError(_('No finished products found for this work order.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pick Finished Products: %s') % self.name,
            'res_model': 'shop.floor.finish.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_move_ids': [(6, 0, all_moves.ids)],
            }
        }


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    total_shop_floor_qty = fields.Float(
        string='Shop Floor Total Quantity',
        compute='_compute_shop_floor_quantities',
        store=True,
        help='Total quantity produced from all work orders'
    )
    
    total_shop_floor_defects = fields.Float(
        string='Shop Floor Total Defects',
        compute='_compute_shop_floor_quantities',
        store=True,
        help='Total defect quantity from all work orders'
    )
    
    qty_produced_shopfloor = fields.Float(
        string='Shop Floor Qty Produced',
        compute='_compute_qty_produced_shopfloor',
        store=True,
        help='Minimum quantity produced across all workorders (bottleneck logic). If no workorders, uses standard qty_produced.'
    )
    
    qty_sent_to_warehouse = fields.Float(
        string='Quantity Sent to Warehouse',
        compute='_compute_qty_sent_to_warehouse',
        store=True,
        help='Total quantity of finished products already sent back to warehouse'
    )
    
    finished_goods_picking_ids = fields.One2many(
        'stock.picking',
        'production_id',
        string='Finished Goods Pickings',
        domain=[('picking_type_id', '=', 'picking_type_id')],
        help='Stock pickings created for transferring finished goods to warehouse'
    )


    @api.depends('workorder_ids.total_quantity_produced', 'workorder_ids.total_defect_quantity')
    def _compute_shop_floor_quantities(self):
        for production in self:
            try:
                total_shop_floor_qty = min(production.workorder_ids.mapped('total_quantity_produced'))

                if total_shop_floor_qty >= 1:
                    production.qty_producing = total_shop_floor_qty
                production.total_shop_floor_qty = total_shop_floor_qty
                production.total_shop_floor_defects = min(production.workorder_ids.mapped('total_defect_quantity'))
            except:
                production.qty_producing = 0
                production.total_shop_floor_qty = 0
                production.total_shop_floor_defects = 0

    @api.depends('workorder_ids.total_quantity_produced', 'qty_produced')
    def _compute_qty_produced_shopfloor(self):
        """Calculate the bottleneck quantity produced - minimum across all workorders"""
        for production in self:
            if production.workorder_ids:
                # Get quantities from all workorders and find the minimum (bottleneck)
                workorder_quantities = production.workorder_ids.mapped('total_quantity_produced')
                # Filter out zero quantities to find the actual minimum production
                non_zero_quantities = [qty for qty in workorder_quantities if qty > 0]
                if non_zero_quantities:
                    production.qty_produced_shopfloor = min(non_zero_quantities)
                else:
                    # If all workorders have 0 production, use 0
                    production.qty_produced_shopfloor = 0
            else:
                # If no workorders, use the standard qty_produced from mrp.production
                production.qty_produced_shopfloor = production.qty_produced

    @api.depends('finished_goods_picking_ids.move_ids.quantity', 'finished_goods_picking_ids.state')
    def _compute_qty_sent_to_warehouse(self):
        """Calculate the total quantity of finished products already sent to warehouse"""
        for production in self:
            # Sum up quantities from finished goods pickings that are done or in progress
            total_sent = 0.0
            for picking in production.finished_goods_picking_ids:
                if picking.state in ['done', 'assigned', 'confirmed']:
                    for move in picking.move_ids:
                        if move.product_id in production.move_finished_ids.mapped('product_id'):
                            total_sent += move.quantity or move.product_uom_qty
            
            production.qty_sent_to_warehouse = total_sent

    def action_pick_component(self):
        """Pick/consume components for this production order"""
        # Check if there are components to consume
        if not self.move_raw_ids:
            raise UserError(_('No components to pick for this production order.'))

        # Get ALL components for this production, not just available ones
        # This allows users to see everything and remove what they don't need
        all_moves = self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty > 0
        )
        
        if not all_moves:
            raise UserError(_('No components found for this production order.'))

        # Create component line values for the picker wizard
        component_line_vals = []
        for component in all_moves:
            # Calculate remaining quantity (total required - already consumed)
            remaining_qty = component.product_uom_qty - component.quantity
            
            # Only add components that still have remaining quantity to pick
            if remaining_qty > 0:
                line_vals = {
                    'product_id': component.product_id.id,
                    # 'workorder_id': component.workorder_id.id if component.workorder_id else False,
                    'available_quantity': component.product_id.virtual_available,
                    'quantity_to_pick': remaining_qty,  # Use remaining quantity instead of full quantity
                    'uom_id': component.product_uom.id,
                }
                component_line_vals.append((0, 0, line_vals))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pick Components: %s') % self.name,
            'res_model': 'shop.floor.production.component.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_component_line_ids': component_line_vals,
            }
        }

    def action_pick_finish_component(self):
        """Pick/produce finished components for this production order"""
        # Check if there's a main product to produce
        if not self.product_id:
            raise UserError(_('No main product defined for this production order.'))
        
        # Calculate the quantity that can be picked based on what's been produced
        # Use total_shop_floor_qty as the basis for available quantity
        available_qty = self.qty_producing or 0.0
        
        # Calculate how much has already been sent to warehouse
        already_sent = self.qty_sent_to_warehouse or 0.0
        
        # Calculate remaining quantity to pick (produced - already sent)
        remaining_qty = available_qty - already_sent
        
        _logger.info(f"[Shop Floor] action_pick_finish_component: production={self.name}, product={self.product_id.name}")
        _logger.info(f"[Shop Floor] Available qty: {available_qty}, already sent: {already_sent}, remaining: {remaining_qty}")
        
        # Only proceed if there's something to pick
        if remaining_qty <= 0:
            raise UserError(_('No finished products available to pick. All produced quantities have already been sent to warehouse.'))
        
        # Create finish line values for the picker wizard
        finish_line_vals = []
        
        # Create a single line for the main product
        line_vals = {
            'product_id': self.product_id.id,
            'workorder_id': False,  # Main product doesn't have a specific workorder
            'available_quantity': remaining_qty,
            'quantity_to_pick': remaining_qty,  # Default to all remaining quantity
            'uom_id': self.product_uom_id.id,
        }
        finish_line_vals.append((0, 0, line_vals))
        
        _logger.info(f"[Shop Floor] Created finish line for {self.product_id.name}: qty_to_pick={remaining_qty}")
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pick Finished Products: %s') % self.name,
            'res_model': 'shop.floor.production.finish.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_finish_line_ids': finish_line_vals,
            }
        }


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    def action_view_current_productivity(self):
        """View current productivity records with quantity information"""
        action = self.env.ref('mrp.mrp_workcenter_productivity_action').read()[0]
        action['domain'] = [
            ('workcenter_id', '=', self.id),
            ('date_end', '=', False)
        ]
        action['context'] = {'default_workcenter_id': self.id}
        action['name'] = _('Current Productivity - %s') % self.name
        return action


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    current_productivity_id = fields.Many2one(
        'mrp.workcenter.productivity',
        string='Current Productivity',
        compute='_compute_current_productivity',
        help='Currently active productivity record for this employee'
    )
    
    total_quantity_today = fields.Float(
        string="Today's Production",
        compute='_compute_today_stats',
        help='Total quantity produced today'
    )

    @api.depends('user_id')
    def _compute_current_productivity(self):
        for employee in self:
            if employee.user_id:
                current_productivity = self.env['mrp.workcenter.productivity'].search([
                    ('user_id', '=', employee.user_id.id),
                    ('date_end', '=', False)
                ], limit=1)
                employee.current_productivity_id = current_productivity
            else:
                employee.current_productivity_id = False

    def _compute_today_stats(self):
        today = fields.Date.today()
        for employee in self:
            if employee.user_id:
                today_productivity = self.env['mrp.workcenter.productivity'].search([
                    ('user_id', '=', employee.user_id.id),
                    ('date_start', '>=', today),
                    ('date_start', '<', today + fields.timedelta(days=1))
                ])
                employee.total_quantity_today = sum(today_productivity.mapped('quantity_produced'))
            else:
                employee.total_quantity_today = 0.0


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',
        help='Production order this picking is related to'
    ) 