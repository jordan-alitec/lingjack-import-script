# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _
from odoo.tools import float_compare


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    production_serial_ids = fields.One2many(
        'production.serial',
        'production_id',
        string='Production Serials',
        copy=False,
    )
    production_serial_count = fields.Integer(
        string='Production Serial Count',
        compute='_compute_production_serial_count',
    )

    @api.depends('production_serial_ids')
    def _compute_production_serial_count(self):
        for production in self:
            production.production_serial_count = len(production.production_serial_ids)

    def action_view_production_serials(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Production Serials'),
            'res_model': 'production.serial',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
            'context': {'default_production_id': self.id, 'default_product_id': self.product_id.id},
        }

    def button_mark_done(self):
        # Capture produced quantity before super() (state may change after)
        produced_qty_by_mo = {}
        for mo in self:
            qty = int(mo.qty_producing) if float_compare(mo.qty_producing, 0, precision_digits=0) > 0 else 0
            produced_qty_by_mo[mo.id] = qty

        result = super().button_mark_done()

        ProductionSerial = self.env['production.serial']
        for mo in self:
            if mo.state != 'done':
                continue
            n = produced_qty_by_mo.get(mo.id, 0)
            if n <= 0:
                continue
            # MFG period from date_finished (PRD: MMM YYYY e.g. DEC 2025)
            dt = mo.date_finished or fields.Datetime.now()
            if isinstance(dt, str):
                dt = datetime.datetime.strptime(dt[:19], '%Y-%m-%d %H:%M:%S')
            mfg_period = dt.strftime('%b %Y').upper()
            location_dest_id = mo.location_dest_id.id if mo.location_dest_id else False
            for _ in range(n):
                name = ProductionSerial._get_next_name(mo.product_id.id, mo.company_id.id)
                ProductionSerial.create({
                    'name': name,
                    'production_id': mo.id,
                    'product_id': mo.product_id.id,
                    'mfg_period': mfg_period,
                    'location_id': location_dest_id,
                    'company_id': mo.company_id.id,
                })
        return result
