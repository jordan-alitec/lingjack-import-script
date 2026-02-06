from odoo import api, fields, models, _
import base64
import json
import logging

_logger = logging.getLogger(__name__)


class QualityCheckClass(models.Model):
    _inherit = 'quality.check'

    def _compute_qty_line(self):
        '''
            To update the default function from odoo of computing the qty line
        '''
        for qc in self:
            if qc.move_line_id:
                qc.qty_line = qc.move_line_id.quantity
            elif qc.picking_id:
                qc.qty_line = qc.picking_id._get_qty_line(qc.product_id.id)
            else:
                qc.qty_line = 0
