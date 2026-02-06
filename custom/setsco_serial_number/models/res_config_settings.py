from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    safety_stock_notification_users = fields.Many2many(
        'res.users',
        string='Safety Stock Notification Users',
        help='Users who will be notified when setsco serial numbers fall below safety stock levels',
        domain=[('active', '=', True)]
    )

    @api.model
    def get_values(self):
        """Get current values for safety stock notification users"""
        res = super().get_values()
        company = self.env.company
        res.update({
            'safety_stock_notification_users': [(6, 0, company.safety_stock_notification_users.ids)]
        })
        return res

    def set_values(self):
        """Set values for safety stock notification users"""
        super().set_values()
        company = self.env.company
        if self.safety_stock_notification_users:
            company.safety_stock_notification_users = self.safety_stock_notification_users
        else:
            company.safety_stock_notification_users = [(5, 0, 0)] 