from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, date=None):
        move = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)
        for invoice in move:
            sale_line_ids = invoice.invoice_line_ids.mapped('sale_line_ids')
            stock_move_ids = self.env['stock.move'].search([('sale_line_id', 'in', sale_line_ids.ids), ('state', '!=', 'cancel')])
            picking_ids = stock_move_ids.mapped('picking_id')
            pick_to_update_ids = picking_ids.filtered(lambda r: r.invoice_state == '2binvoiced')
            pick_to_update_ids.write({'invoice_state': 'invoiced',
                                      'invoice_id': invoice.id})
        return move
