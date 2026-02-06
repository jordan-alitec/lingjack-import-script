# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

class ScrapBackdateWizardInherit(models.TransientModel):
    _inherit = 'sh.scrap.backdate.wizard'

    def assign_backdate(self):

        super(ScrapBackdateWizardInherit, self).assign_backdate()

        if self.company_id.backdate_for_scrap:

            for stock_scrap in self.scrap_ids:

                stock_moves = self.env['stock.move'].search(
                    ['|', ('scrap_id', '=', stock_scrap.id), ('origin', '=', stock_scrap.name)])

                account_moves = self.env['account.move'].search(
                    [('stock_move_id', 'in', stock_moves.ids)])
                valuation_layers = self.env['stock.valuation.layer'].search(
                    [('stock_move_id', 'in', stock_moves.ids)])

                for account_move in account_moves:
                    account_move.button_draft()
                    account_move.name = False
                    account_move.date = self.date_done
                    account_move.action_post()

                for layer in valuation_layers:
                    self.env.cr.execute("""
                        Update stock_valuation_layer set create_date='%s' where id=%s; 
                    """ % (self.date_done, layer.id))
