# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductionSerial(models.Model):
    _name = 'production.serial'
    _description = 'Production Serial (Unit ID Registry)'
    _order = 'id desc'

    name = fields.Char(
        string='Service ID',
        required=True,
        copy=False,
        readonly=True,
        index=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='restrict',
    )
    default_code = fields.Char(
        string='Com No',
        related='product_id.default_code',
        store=True,
        readonly=True,
    )
    mfg_period = fields.Char(
        string='MFG',
        required=True,
        help='Manufacturing period (e.g. DEC 2025)',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Location',
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    state = fields.Selection(
        [
            ('active', 'Active'),
            ('cancelled', 'Cancelled'),
        ],
        string='State',
        default='active',
        required=True,
    )

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Service ID must be unique.'),
    ]

    @api.model
    def _get_next_name(self, product_id, company_id):
        """Generate next Service ID: <category_prefix><running_number> (company-dependent sequence)."""
        product = self.env['product.product'].browse(product_id)
        company = self.env['res.company'].browse(company_id)
        prefix = 'PS'
        if product.categ_id.production_serial_prefix:
            prefix = (product.categ_id.production_serial_prefix or '').strip() or prefix
        seq = self.with_company(company).env['ir.sequence'].next_by_code('production.serial')
        if not seq:
            raise ValidationError(_(
                'Sequence "Production Serial" is missing. '
                'Please create it in Settings > Technical > Sequences.'
            ))
        return prefix + seq
