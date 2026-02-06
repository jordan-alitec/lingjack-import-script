from odoo import models, fields

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    receipt_category_id = fields.Many2one('receipt.category',string='Receipt Category')
    cheque_number = fields.Char(string='Cheque Number')
    analytic_account_id = fields.Many2one('account.analytic.account',string='Cost Center')

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals['receipt_category_id'] = self.receipt_category_id.id
        payment_vals['analytic_account_id'] = self.analytic_account_id.id
        payment_vals['cheque_number'] = self.cheque_number
        return payment_vals
