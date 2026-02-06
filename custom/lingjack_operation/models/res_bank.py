from odoo import fields, models

class ResBank(models.Model):
    _inherit = 'res.bank'

    bank_code = fields.Char(string="Bank Code")
    branch_code = fields.Char(string="Branch Code")
