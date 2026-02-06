# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LingjackEditProductTemplateWizard(models.TransientModel):
    _name = 'lingjack.edit.product.template.wizard'
    _description = 'Lingjack - Edit Product (HS, Origin, Weight)'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    product_id = fields.Many2one('product.product', string='Product Variant', readonly=True)
    hs_code = fields.Char(string='HS Code')
    country_of_origin = fields.Many2one('res.country', string='Country of Origin')
    weight = fields.Float(string='Weight (kg)')

    @api.model
    def default_get(self, fields_list):
        """Pre-fill fields from the product template or product variant."""
        res = super().default_get(fields_list)
        
        # Check for product variant first
        product_variant_id = self.env.context.get('default_product_id')
        if product_variant_id:
            product = self.env['product.product'].browse(product_variant_id)
            res.update({
                'product_id': product.id,
                'product_tmpl_id': product.product_tmpl_id.id,
                'hs_code': product.hs_code,
                'country_of_origin': product.country_of_origin.id if product.country_of_origin else False,
                'weight': product.weight,
            })
        else:
            # Fall back to product template
            product_tmpl_id = self.env.context.get('default_product_tmpl_id')
            if product_tmpl_id:
                product = self.env['product.template'].browse(product_tmpl_id)
                res.update({
                    'product_tmpl_id': product.id,
                    'hs_code': product.hs_code,
                    'country_of_origin': product.country_of_origin.id if product.country_of_origin else False,
                    'weight': product.weight,
                })
        return res

    def action_apply(self):
        """Apply changes to either product variant or template."""
        self.ensure_one()
        vals = {}
        if self.hs_code:
            vals['hs_code'] = self.hs_code
        if self.country_of_origin:
            vals['country_of_origin'] = self.country_of_origin.id
        if self.weight:
            vals['weight'] = self.weight
        
        if vals:
            # Update product variant if specified, otherwise update template
            if self.product_id:
                self.product_id.sudo().write(vals)
            elif self.product_tmpl_id:
                self.product_tmpl_id.sudo().write(vals)
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
