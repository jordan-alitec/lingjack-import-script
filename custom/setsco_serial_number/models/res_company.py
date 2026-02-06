from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    safety_stock_notification_users = fields.Many2many(
        'res.users',
        string='Safety Stock Notification Users',
        help='Users who will be notified when setsco serial numbers fall below safety stock levels',
        domain=[('active', '=', True)]
    ) 