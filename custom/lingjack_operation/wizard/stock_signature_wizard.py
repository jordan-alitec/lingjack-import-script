from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockSignatureWizard(models.TransientModel):
    _name = 'stock.signature.wizard'
    _description = 'Stock Signature Wizard'

    picking_id = fields.Many2one('stock.picking', required=True)

    customer_signature = fields.Binary(string="Customer Signature", required=True)
    signature_name = fields.Char(string="Name", required=True)
    signature_date = fields.Datetime(string="Date", default=fields.Datetime.now, required=True)

    def action_confirm(self):
        self.ensure_one()

        if not self.customer_signature:
            raise ValidationError(_("Customer Signature is required."))

        self.picking_id.sudo().write({
            'customer_signature': self.customer_signature,
            'signature_name': self.signature_name,
            'signature_date': self.signature_date,
        })

    @api.onchange('customer_signature')
    def _onchange_customer_signature(self):
        if self.customer_signature:
            self.signature_date = fields.Datetime.now()
