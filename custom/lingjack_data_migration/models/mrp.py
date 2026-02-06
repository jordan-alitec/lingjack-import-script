# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MRPProduction(models.Model):
    _inherit = 'mrp.production'

    old_so_id = fields.Char(string='Old SO ID')
    old_swo_id = fields.Char(string='Old SWO ID')
    old_pwo_id = fields.Char(string='Old PWO ID')
    old_so_number = fields.Char(string='Old SO Number')
    old_swo_number = fields.Char(string='Old SWO Number')
    old_pwo_number = fields.Char(string='Old PWO Number')
    
    old_qty_produced = fields.Float('Old Quantity Produced', default=0.0)
    # import_confirmed = fields.Boolean(string='Import Confirmed', default=False)
    # import_started = fields.Boolean(string='Import Started', default=False)
    # import_planned = fields.Boolean(string='Import Planned', default=False)

    def button_set_done(self):

        for mo in self:
            mo.workorder_ids.qty_produced = mo.product_qty
            mo.workorder_ids.total_produced = mo.product_qty
            mo.button_mark_done()
        return True

    def swap_old_name(self):
        for mo in self:
            mo.name = mo.old_pwo_number
        return True

    def action_import_confirm(self):
        for rec in self:
            for move in rec.move_raw_ids:
                move.warehouse_id = 1
            rec.action_confirm()
        return True
       

