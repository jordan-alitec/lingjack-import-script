from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_followup_recipient(self):
        followup_child = self.child_ids.filtered(lambda partner: partner.type == 'followup')
        return ','.join(followup_child.mapped('email_formatted'))