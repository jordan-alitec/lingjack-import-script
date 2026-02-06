from odoo import models

class MrpUnbuild(models.Model):
    _inherit = 'mrp.unbuild'

    def write(self,vals):

        res = super().write(vals)
        if 'state' in vals and vals['state'] == 'done' and self.mo_id:
            stock_moves = self.env['stock.move'].search(['|',('unbuild_id','=',self.id),('consume_unbuild_id','=',self.id)])
            product_moves = self.env['stock.move.line'].search([('move_id','in',stock_moves.ids)])
            account_moves = self.env['account.move'].search([('stock_move_id','in',stock_moves.ids)])
            valuation_layers = self.env['stock.valuation.layer'].sudo().search([('stock_move_id','in',stock_moves.ids)])

            for account_move in account_moves:
                account_move.button_draft()
                account_move.name = '/'
                account_move.date = self.mo_id.date_start
                account_move.action_post()

            for move in stock_moves:
                move.date = self.mo_id.date_start
                move.remarks_for_mrp = self.mo_id.remarks if self.mo_id.remarks else ''

            for move in product_moves:
                move.date = self.mo_id.date_start

            for layer in valuation_layers:
                self.env.cr.execute("""
                    Update stock_valuation_layer set create_date='%s' where id=%s;
                """ %(self.mo_id.date_start, layer.id))

        return res
