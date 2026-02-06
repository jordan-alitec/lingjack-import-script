from odoo import models, fields, api

class StockRoute(models.Model):
    _inherit = 'stock.route'

    is_manufacture = fields.Boolean(
        string='Is Manufacture Route',
        help='Check this box if this route is used for manufacturing operations',
        default=False
    ) 