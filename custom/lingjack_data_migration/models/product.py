# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def api_create_non_stock(self, vals):
        """
        API endpoint to create a consumable (non-stock) product.
        """
        if not vals.get('name'):
            raise ValidationError("Product name is required")

        product_name = vals.get('name').strip()
        existing_product = self.search([('name', '=', product_name)], limit=1)
        if existing_product:
            return {
                'status': 'exists',
                'product_id': existing_product.id,
                'name': existing_product.name,
            }

        category = self.env['product.category'].search([('name', '=', 'Non-Stock Items')], limit=1)
        if not category:
            category = self.env['product.category'].create({
                'name': 'Non-Stock Items'
            })

        vals.update({
            'type': 'consu',        
            'sale_ok': True,
            'purchase_ok': True,
            'categ_id': category.id,  
        })

        vals.pop('company_id', None)
        # if not vals.get('company_id'):
        #     vals['company_id'] = self.env.company.id

        try:
            new_product = self.create(vals)

            return {
                'status': 'created',
                'product_id': new_product.id,
                'name': new_product.name,
            }

        except Exception as e:
            raise ValidationError(f"Error creating non-stock product: {str(e)}")

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    import_newly_created = fields.Boolean(default=False)

    @api.model
    def non_stock_api_batch_create(self, names):
        """
        Batch create non-stock products.
        names: list of product names to check/create
        """
        if not names:
            return {'created': [], 'existing': []}

        # Filter out empty names and duplicates
        unique_names = list(set([str(n).strip() for n in names if n and str(n).strip()]))
        
        # Find existing products
        # We search product.product to be sure we don't create duplicates even if template exists?
        # But if we create a template, a product is created.
        # Let's search product.product to follow the logic of "product" existence.
        existing_products = self.env['product.product'].search([('name', 'in', unique_names)])
        existing_names = existing_products.mapped('name')
        
        # Determine which ones need to be created
        to_create_names = [n for n in unique_names if n not in existing_names]
        
        if not to_create_names:
            return {
                'created': [],
                'existing': existing_names,
            }

        # Get or create category
        category = self.env['product.category'].search([('name', '=', 'Non-Stock Items')], limit=1)
        if not category:
            category = self.env['product.category'].create({
                'name': 'Non-Stock Items'
            })
            
        created_products = []
        for name in to_create_names:
             vals = {
                'name': name,
                'type': 'consu',        
                'sale_ok': True,
                'purchase_ok': True,
                'categ_id': category.id,
            }
             # Use try-except per record to avoid failing the whole batch if one fails
             try:
                 # creating product.template effectively creates product.product too for non-variants
                 new_product = self.create(vals)
                 created_products.append(new_product.name)
             except Exception as e:
                 _logger.error(f"Failed to create non-stock product {name}: {str(e)}")

        return {
            'created': created_products,
            'existing': existing_names,
        }
