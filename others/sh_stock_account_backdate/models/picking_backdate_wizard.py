# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

class PickngBackdateWizardInherit(models.TransientModel):
    _inherit = 'sh.picking.backdate.wizard'

    def assign_backdate(self):
        super(PickngBackdateWizardInherit, self).assign_backdate()

        if self.company_id.backdate_for_picking:

            for stock_picking in self.stock_picking_ids:
                stock_moves = self.env['stock.move'].search(
                    [('picking_id', '=', stock_picking.id)])
                account_moves = self.env['account.move'].search(
                    [('stock_move_id', 'in', stock_moves.ids)])
                valuation_layers = self.env['stock.valuation.layer'].search(
                    [('stock_move_id', 'in', stock_moves.ids)])

                for account_move in account_moves:
                    account_move.button_draft()
                    account_move.name = False
                    account_move.date = self.scheduled_date
                    account_move.action_post()

                for layer in valuation_layers:
                    self.env.cr.execute("""
                        Update stock_valuation_layer set create_date='%s' where id=%s; 
                    """ % (self.scheduled_date, layer.id))
