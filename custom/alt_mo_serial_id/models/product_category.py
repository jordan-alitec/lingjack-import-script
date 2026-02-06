# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    production_serial_prefix = fields.Char(
        string='Production Serial Prefix',
        help='Prefix used for Service ID (e.g. CHAIR). Used with company-wide sequence.',
    )
