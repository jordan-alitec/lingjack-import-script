from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"
    def _message_auto_subscribe_notify(self, partner_ids, template):
        """Filter out partners whose users have disabled assignment notifications.
        
        Only send notifications to users who have `send_assign_notify` enabled.
        """
        if not partner_ids:
            return
            
        # Filter partner_ids based on user preference
        filtered_partner_ids = []
        for partner_id in partner_ids:
            partner = self.env['res.partner'].browse(partner_id)
            user = partner.user_ids[:1]
            if user and user.send_assign_notify:
                filtered_partner_ids.append(partner_id)
        
        # Only call super if there are partners to notify
        if filtered_partner_ids:
            super()._message_auto_subscribe_notify(filtered_partner_ids, template)

