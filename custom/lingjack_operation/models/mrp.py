from odoo import models, fields

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    remark = fields.Text(string="Remark")
