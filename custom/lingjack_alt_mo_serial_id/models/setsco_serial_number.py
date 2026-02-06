# -*- coding: utf-8 -*-

from odoo import fields, models


class SetscoSerialNumber(models.Model):
    _inherit = 'setsco.serial.number'

    production_serial_id = fields.Many2one(
        'production.serial',
        string='Production Serial (Service ID)',
        ondelete='set null',
        copy=False,
    )
