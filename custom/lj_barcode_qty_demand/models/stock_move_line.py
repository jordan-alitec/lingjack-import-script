# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    actual_reserve_qty = fields.Float(
        string='Actual Reserve Qty',
        help='Alternative reserved quantity used by the barcode app for qty demand.',
        compute='_compute_actual_reserve_qty',
        store=False,
    )

    # @api.depends('move_id', 'quantity')
    def _compute_actual_reserve_qty(self):
        for line in self:

            # Use stock.move.actual_requested_qty if that field exists; otherwise fallback to current line reservation quantity
            if ('actual_requested_qty' in line.move_id._fields and line.move_id.picking_id.production_count != 0) and line.picking_id.picking_type_id.sequence_code != 'SFP' or not line.move_id.product_id.is_storable:

                line.actual_reserve_qty = line.move_id.quantity_requested
            else:
                line.actual_reserve_qty = line.move_id.product_uom_qty

    def _get_fields_stock_barcode(self):
        fields_list = super()._get_fields_stock_barcode()
        if 'actual_reserve_qty' not in fields_list:
            fields_list.append('actual_reserve_qty')
        return fields_list
