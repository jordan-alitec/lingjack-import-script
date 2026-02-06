from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    send_assign_notify = fields.Boolean(
        string="Send assignment notification",
        help="If enabled, when this user is auto-subscribed as follower (e.g., assigned via tracked user field), send the standard 'You have been assigned' notification.",
        default=False,
    )


    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['send_assign_notify']


