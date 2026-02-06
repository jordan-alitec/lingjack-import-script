# -*- coding: utf-8 -*-
#import of odoo
from odoo import fields, models

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    available_quantity = fields.Float(
        string='Free to Use',
    )
