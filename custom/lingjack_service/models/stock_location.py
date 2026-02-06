from odoo import models, fields, api
from odoo.exceptions import UserError


class StockLocation(models.Model):
    _inherit = 'stock.location'
    
    customer_id = fields.Many2many(
        'res.partner',
        'stock_location_partner_rel',  # relation table name
        'location_id',                 # column referring to stock.location
        'partner_id',                  # column referring to res.partner
        string='Delivery Address',
    )