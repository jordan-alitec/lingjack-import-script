# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    website_url = fields.Char(
        string='Website URL',
        help='Base URL for product labels/QR (e.g. product page). If empty, company website is used when printing labels.'
    )
