# -*- coding: utf-8 -*-

from odoo import models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def button_mark_done(self):
        result = super().button_mark_done()

        ProductionSerial = self.env['production.serial']
        for mo in self:
            if mo.state != 'done':
                continue
            if not getattr(mo.product_id, 'requires_setsco_serial', False):
                continue
            setsco_serials = mo.setsco_serial_ids.sorted(key=lambda s: s.id)
            if not setsco_serials:
                continue
            production_serials = ProductionSerial.search(
                [('production_id', '=', mo.id)],
                order='id',
            )
            if not production_serials:
                continue
            n = min(len(production_serials), len(setsco_serials))
            for i in range(n):
                prod_serial = production_serials[i]
                setsco_serial = setsco_serials[i]
                prod_serial.setsco_serial_id = setsco_serial.id
                setsco_serial.production_serial_id = prod_serial.id

        return result
