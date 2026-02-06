from odoo import models, fields

class UoM(models.Model):
    _inherit = 'uom.uom'  # Inherit the base model

    pdf_printing = fields.Char(string="PDF Printing")