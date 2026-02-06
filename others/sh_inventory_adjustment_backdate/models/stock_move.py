# -*- coding: utf-8 -*-
# Part of Softhealer Technologies

from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    remarks_for_inventory_adj = fields.Text(
        string="Remarks for Inventory Adjustment")

    def _check_stock_account_installed(self):
        account_app = self.env['ir.module.module'].sudo().search([('name','=','stock_account')],limit=1)
        if account_app.state != 'installed':
            return False
        else:
            return True

    # FOR BACKDATE INVENTORY ADJUSTMENT

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder)

        for rec in res:
            backdate = self.env.context.get('sh_backdate')
            if backdate:
                backdate_remark = self.env.context.get('sh_backdate_remark')
                rec.write({
                    "date": backdate,
                    "remarks_for_inventory_adj": backdate_remark
                })

            rec.move_line_ids.date = rec.date
            if self._check_stock_account_installed():
                account_moves = self.env['account.move'].search(
                    [('stock_move_id', 'in', rec.ids)]
                )
                account_moves.button_draft()
                account_moves.name = False
                account_moves.date = rec.date
                account_moves.action_post()
                valuation_layers = self.env["stock.valuation.layer"].search([
                    ('stock_move_id', 'in', rec.ids)
                ])
                if valuation_layers and rec.date:
                    valuation_layer_ids = tuple(valuation_layers.ids)

                    if len(valuation_layer_ids) == 1:
                        valuation_layer_ids = (valuation_layer_ids[0],)
                    query = """
                        UPDATE stock_valuation_layer
                        SET create_date = %s
                        WHERE id IN %s;
                    """
                    self.env.cr.execute(query, (rec.date, valuation_layer_ids))

        return res

