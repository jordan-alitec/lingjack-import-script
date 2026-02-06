# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    quantity_requested = fields.Float(string='Quantity Requested', default=0.0, help='Requested by production manager for internal transfer')

    # Mrp Production that required to see
    stock_item = fields.Boolean(
        string='Stock Item',
        related='product_id.product_tmpl_id.stock_item',
        store=False,
        readonly=True,
    )
    on_hand_qty = fields.Float(
        string='On Hand Quantity',
        compute='_compute_on_hand_and_forecast_qty',
        digits='Product Unit of Measure',
        store=False
    )
    forecast_qty = fields.Float(
        string='Forecast Quantity',
        compute='_compute_on_hand_and_forecast_qty',
        digits='Product Unit of Measure',
        store=False
    )

    committed_qty = fields.Float(
        string='Committed Qty',
        compute='_compute_committed_qty',
        digits='Product Unit of Measure',
        help='Total quantity demanded across all manufacturing orders for this component'
    )

    # Component to track how much already request
    actual_requested_qty = fields.Float(
        string='Total Actual Requested Quantity',
        digits='Product Unit of Measure',
        store=True,
        compute='_compute_source_requested_qty',
        help='Total quantity requested to pick '
    )
    location_id = fields.Many2one(domain="[('warehouse_id','=',warehouse_id),('usage','=','internal')]")
    # Link to original raw material move for pick component transfers
    move_raw_id = fields.Many2one(
        'stock.move',
        string='Raw Material Move',
        help='Original raw material move from manufacturing order'
    )

    def test_trigger_source_requested_qty(self):
        for rec in self:
            rec._compute_source_requested_qty()

    @api.depends('move_orig_ids')
    def _compute_source_requested_qty(self):
        for rec in self:
            origin_moves = rec.move_orig_ids

            # Sum of requested quantities from origin moves not done/cancel
            pending_qty = sum(
                origin_moves
                .filtered(lambda m: m.state not in ('done', 'cancel'))
                .mapped('quantity_requested')
            )

            # Sum of actual quantity from done origin moves
            done_qty = sum(
                origin_moves
                .filtered(lambda m: m.state == 'done')
                .mapped('quantity')
            )

            #  3. Subtract the actual_requested_qty of *other* destination moves (excluding rec)
            other_dest_moves = origin_moves.mapped('move_dest_ids').filtered(lambda m: m != rec)
            unrelated_qty = sum(other_dest_moves.mapped('actual_requested_qty'))

            rec.actual_requested_qty = pending_qty + done_qty - unrelated_qty

    @api.depends('product_id', 'raw_material_production_id', 'state', 'product_uom_qty')
    def _compute_committed_qty(self):
        for move in self:
            if move.raw_material_production_id and move.state not in ['done', 'cancel']:
                # Get all active manufacturing orders' stock moves for this product
                domain = [
                    ('product_id', '=', move.product_id.id),
                    ('raw_material_production_id', '!=', False),
                    ('state', 'not in', ['done', 'cancel']),
                ]
                moves = self.env['stock.move'].search(domain)
                move.committed_qty = sum(moves.mapped('product_uom_qty'))
            else:
                move.committed_qty = 0.0

    @api.depends('product_id', 'product_uom_qty', 'raw_material_production_id.state')
    def _compute_on_hand_and_forecast_qty(self):
        for line in self:
            product = line.product_id
            mo_state = line.raw_material_production_id.state if line.raw_material_production_id else 'draft'

            if not product:
                line.on_hand_qty = 0.0
                line.forecast_qty = 0.0
                continue

            if product.is_storable:
                # On-hand quantity
                line.on_hand_qty = product.qty_available
                if mo_state != 'draft':
                    # Exclude this line's requirement from forecasted quantity
                    line.forecast_qty = product.virtual_available + line.product_uom_qty
                else:
                    line.forecast_qty = product.virtual_available
            else:
                # Default values
                line.on_hand_qty = 0.0
                line.forecast_qty = 0.0

    def action_open_lot_selection(self):
        """Open lot selection for this move in lot selection mode"""
        self.ensure_one()
        
        if not self.product_id.tracking in ['lot', 'serial']:
            raise UserError(_('This product does not require lot tracking.'))
        
        # Check if we're coming from lot selection wizard
        wizard_id = self.env.context.get('lot_selection_wizard_id')
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Lot for %s') % self.product_id.display_name,
            'res_model': 'stock.move',
            'res_id': self.id,
            'views': [[self.env.ref('mrp.view_mrp_stock_move_operations').id, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'lot_selection_mode': True,
                'default_product_id': self.product_id.id,
                'default_product_uom_qty': self.product_uom_qty,
                'default_product_uom': self.product_uom.id,
                'lot_selection_wizard_id': wizard_id,
                'return_to_wizard': True,
            }
        }


    def action_save_and_return_to_wizard(self):
        """Save the move and return to lot selection wizard"""
        self.ensure_one()
        
        # Save the move
        self.write({})
        
        # Get wizard ID from context
        wizard_id = self.env.context.get('lot_selection_wizard_id')
        
        if wizard_id:
            # Return to the lot selection wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Lot Selection Required'),
                'res_model': 'lot.selection.wizard',
                'res_id': wizard_id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            # Fallback to normal close
            return {'type': 'ir.actions.act_window_close'}


