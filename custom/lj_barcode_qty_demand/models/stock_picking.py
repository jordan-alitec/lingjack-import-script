# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_fields_stock_barcode(self):
        fields_list = super()._get_fields_stock_barcode()
        # Ensure the production_count is included in the payload if available on the model
        if 'production_count' not in fields_list:
            fields_list.append('production_count')
        return fields_list 