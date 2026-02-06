from odoo import models, fields, api, _


class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    requires_setsco_serial = fields.Boolean(
        string='Requires Setsco Serial Numbers',
        default=False,
        readonly=False,
        help='Check this box if products in this category require setsco serial number tracking in manufacturing and delivery operations'
    )

    is_setsco_label = fields.Boolean(
        string='Is Setsco Label',
        default=False,
        readonly=False,
        help='Check this box if products in this category should be excluded from two-step manufacturing pick component transfer notes'
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    product_category_id = fields.Many2one('product.category', string='Product Category')

    setsco_category_id = fields.Many2one(
        'setsco.category',
        string='Serial Category',
        readonly=False,
        help='Link this product to a specific Setsco category'
    )

    requires_setsco_serial = fields.Boolean(
        string='Requires Setsco Serial Numbers',
        compute='_compute_requires_setsco_serial',
        store=True,
        readonly=False,
        help='Check this box if this product requires setsco serial number tracking in manufacturing and delivery operations'
    )
    
    is_setsco_label = fields.Boolean(
        string='Is Setsco Label',
        compute='_compute_is_setsco_label',
        store=True,
        readonly=False,
        help='Check this box if this product should be excluded from two-step manufacturing pick component transfer notes'
    )


    @api.depends('categ_id.requires_setsco_serial')
    def _compute_requires_setsco_serial(self):
        for record in self:
            record.requires_setsco_serial = record.categ_id.requires_setsco_serial if record.categ_id else False

    @api.depends('categ_id.is_setsco_label')
    def _compute_is_setsco_label(self):
        for record in self:
            record.is_setsco_label = record.categ_id.is_setsco_label if record.categ_id else False


class ProductProduct(models.Model):
    _inherit = 'product.product'

    requires_setsco_serial = fields.Boolean(
        string='Requires Setsco Serial Numbers',
        related='product_tmpl_id.requires_setsco_serial',
        readonly=False,
        help='Check this box if this product requires setsco serial number tracking in manufacturing and delivery operations'
    )
    
    is_setsco_label = fields.Boolean(
        string='Is Setsco Label',
        related='product_tmpl_id.is_setsco_label',
        readonly=False,
        help='Check this box if this product should be excluded from two-step manufacturing pick component transfer notes'
    )

    setsco_category_id = fields.Many2one(
        related='product_tmpl_id.setsco_category_id',
        readonly=False,
        store=True,
        string='Serial Category'
    )