from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    delivery_note = fields.Text(
        string="Delivery Note",
        related='company_id.delivery_note_text',
        readonly=False
    )

    proforma_invoice_text = fields.Text(
        string="Pro-Forma invoice Note",
        related='company_id.proforma_invoice_text',
        readonly=False
    )

class ResCompany(models.Model):
    _inherit = 'res.company'

    delivery_note_text = fields.Text(string="Notes on Delivery Order")
    proforma_invoice_text = fields.Text(
        string="Pro-Forma invoice Note"
    )
