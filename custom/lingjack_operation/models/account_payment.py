from odoo import models, fields ,_,api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    receipt_category_id = fields.Many2one('receipt.category',string='Receipt Category')
    cheque_number = fields.Char(string='Cheque Number')
    analytic_account_id = fields.Many2one('account.analytic.account',string='Cost Center')
    specific_approver_id = fields.Many2one('res.users', string="Specific Approver (If any)")

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        line_vals_list = super()._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals,force_balance=force_balance)
        if self.analytic_account_id:
            analytic_distribution = {
                str(self.analytic_account_id.id): 100
            }
            for line_vals in line_vals_list:
                account_id = line_vals.get('account_id')
                if not account_id:
                    continue

                account = self.env['account.account'].browse(account_id)
                if account.account_type in ('income', 'expense'):
                    line_vals['analytic_distribution'] = analytic_distribution

        return line_vals_list

    def _get_aml_default_display_name_list(self):
        self.ensure_one()
        if self.memo:
            return [
                ('memo', self.memo),
            ]
        return [
            ('memo', _("No Memo")),
        ]

class ReceiptCategory(models.Model):
    _name = 'receipt.category'
    _description = 'Receipt Category'

    name = fields.Char(string='Category Name', required=True)
