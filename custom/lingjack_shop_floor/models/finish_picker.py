# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShopFloorFinishPicker(models.TransientModel):
    _name = 'shop.floor.finish.picker'
    _description = 'Shop Floor Finish Product Picker'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        required=True,
        readonly=True
    )
    
    move_ids = fields.Many2many(
        'stock.move',
        string='Available Finished Products',
        readonly=True
    )
    
    finish_line_ids = fields.One2many(
        'shop.floor.finish.line',
        'picker_id',
        string='Finished Products to Pick'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if 'workorder_id' in self.env.context:
            workorder_id = self.env.context['workorder_id']
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            
            # Get finished products for this work order
            finished_moves = workorder.move_finished_ids.filtered(
                lambda m: m.state in ('assigned', 'waiting', 'confirmed') and m.product_uom_qty > 0
            )
            
            if finished_moves:
                res['move_ids'] = [(6, 0, finished_moves.ids)]
                
                # Create lines for each finished product
                line_vals = []
                for move in finished_moves:
                    # Calculate how much can be produced based on workorder progress
                    max_producible = min(move.product_uom_qty, workorder.qty_production or move.product_uom_qty)
                    
                    line_vals.append((0, 0, {
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'available_quantity': max_producible,
                        'quantity_to_pick': 0.0,  # User will fill this
                        'uom_id': move.product_uom.id,
                    }))
                res['finish_line_ids'] = line_vals
        
        return res

    def action_pick_finished_products(self):
        """Execute the finished product picking"""
        self.ensure_one()
        
        # Validate that at least one product has quantity > 0
        lines_to_pick = self.finish_line_ids.filtered(lambda l: l.quantity_to_pick > 0)
        if not lines_to_pick:
            raise UserError(_('Please specify quantity to pick for at least one finished product.'))
        
        # Process each finished product line
        for line in lines_to_pick:
            move = line.move_id
            if move and move.state not in ('done', 'cancel'):
                # Update the move's quantity_done
                move.quantity_done = min(line.quantity_to_pick, move.product_uom_qty)
                _logger.info(f"[Shop Floor] Updated finished move {move.id} quantity_done: {move.quantity_done}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Finished Products Picked'),
                'message': _('Finished products have been successfully picked for work order %s') % self.workorder_id.name,
                'type': 'success',
                'sticky': False,
            }
        }


class ShopFloorFinishLine(models.TransientModel):
    _name = 'shop.floor.finish.line'
    _description = 'Shop Floor Finish Product Line'

    picker_id = fields.Many2one(
        'shop.floor.finish.picker',
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
        readonly=True
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
            if line.quantity_to_pick > line.available_quantity:
                raise ValidationError(_('Cannot pick more than available quantity for %s.') % line.product_id.name) 