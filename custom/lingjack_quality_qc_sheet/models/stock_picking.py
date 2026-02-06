from odoo import api, fields, models, _
import base64
import json
import logging

_logger = logging.getLogger(__name__)


class StockPickingClass(models.Model):
    _inherit = 'stock.picking'

    def _get_qty_line(self, product_id):
        '''
            This function is to return the total qty for specific product in the stock picking
            (Mainly for quality check as quality check default control per product doesnt work for qty calculation)
        '''

        return sum(
            move.quantity for move in self.move_ids_without_package
            if move.product_id.id == product_id
        )
