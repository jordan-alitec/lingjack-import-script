# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging
from datetime import timedelta
_logger = logging.getLogger(__name__)


class SaleWorkOrder(models.Model):
    _inherit = 'sale.work.order'

    old_swo_number = fields.Char(string='Old SWO Number')
    old_pwo_number = fields.Char(string='Old PWO Number')
    old_so_number = fields.Char(string='Old SO Number')
    old_issue_date = fields.Datetime(string='Old Issue Date')
    issue_by = fields.Char(string='Old Issue By')

    def swap_old_name(self):
        """Replace Odoo-generated name with old_swo_number from Excel."""
        for record in self:
            if record.old_swo_number:
                record.request_date = record.old_issue_date - timedelta(hours=8)
                record.name = record.old_swo_number
        return True

    def action_confirm(self):
        res = super().action_confirm()
        return res


    def action_compute_qty_produced(self):
        for line in self.line_ids:
           line._compute_qty_produced()
           line.qty_in_stock = line.qty_produced
           line._compute_state()
        return True

class SaleWorkOrderLine(models.Model):
    _inherit = 'sale.work.order.line'

    old_pwo_number = fields.Char(string='Old PWO Number')

 