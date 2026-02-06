# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrderLineChangeUnitPriceWizard(models.TransientModel):
    _name = 'sale.order.line.change.unit.price.wizard'
    _description = 'Change Unit Price Wizard'

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=True,
        readonly=True
    )
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        digits='Product Price',
        help='Unit price for the sale order line'
    )

    @api.constrains('price_unit')
    def _check_price_unit(self):
        """Ensure unit price is valid"""
        for record in self:
            if record.price_unit < 0:
                raise UserError(_('Unit price cannot be negative.'))

    @api.model
    def default_get(self, fields_list):
        """Set default values from the sale order line"""
        res = super().default_get(fields_list)
        if 'sale_order_line_id' in self.env.context:
            line_id = self.env.context['sale_order_line_id']
            line = self.env['sale.order.line'].browse(line_id)
            if line.exists():
                res.update({
                    'sale_order_line_id': line.id,
                    'price_unit': line.price_unit,
                })
        return res

    def action_save_price(self):
        """Save the unit price to the sale order line and restart validation if needed"""
        self.ensure_one()
        
        if not self.sale_order_line_id:
            raise UserError(_('No sale order line selected.'))
        
        # Check if the sale order is locked
        if self.sale_order_line_id.order_id.locked:
            raise UserError(_('Cannot change unit price on a locked sale order.'))
        
        # Get sale order before update
        sale_order = self.sale_order_line_id.order_id
        
        # Update the sale order line
        self.sale_order_line_id.write({
            'price_unit': self.price_unit,
        })
        
        # Restart validation if sale order has active reviews and is in draft/sent state
        # This ensures that when unit price changes, the validation process restarts
        # if (hasattr(sale_order, 'review_ids') and 
        #     sale_order.review_ids and 
        #     sale_order.state in ['draft', 'sent']):
        sale_order.state = 'draft'
        # sale_order.request_validation() No need request Validation 
        
        return {'type': 'ir.actions.act_window_close'}

