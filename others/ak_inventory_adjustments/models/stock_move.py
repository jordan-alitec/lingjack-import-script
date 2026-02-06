from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    inventory_id = fields.Many2one(
        "stock.inventory", "Stock Inventory", check_company=True
    )

    def _generate_valuation_lines_data(self, partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description):
        res = super()._generate_valuation_lines_data(partner_id,qty,debit_value,credit_value,debit_account_id,credit_account_id,svl_id,description)
        if self._context.get('ac_include_analytic_account',False) and self.inventory_id.analytic_account_id:
            res['credit_line_vals']['analytic_distribution'] = {self.inventory_id.analytic_account_id.id:100}
            res['debit_line_vals']['analytic_distribution'] = {self.inventory_id.analytic_account_id.id:100}
        return res