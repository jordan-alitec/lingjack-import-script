# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    qr_code = fields.Image(string="QR Code", copy=False, attachment=True, max_width=1024, max_height=1024)