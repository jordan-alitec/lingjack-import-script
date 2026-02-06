# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class digitalUsers(models.Model):
    _inherit = "res.users"

    digital_signature = fields.Binary(string="Signature")

    def writeSign(self, vals):
        if "digital_signature" in vals and len(vals) == 1:
            self.sudo().write(vals)
