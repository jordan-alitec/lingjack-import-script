from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    old_sale_order = fields.Integer(string='Old Sale Order ID')

    @api.model
    def api_create_sale_order(self, vals):
        """
        API method to create a sale order with custom logic for data migration.

        :param vals: Dictionary containing sale order values
        :return: Created sale order record
        """
        try:
            _logger.info(f"Creating sale order with values: {vals}")
            order_name = vals.get('name', 'Unknown Order')
            company = vals.get('company_id')
            company_id = self.env['res.company'].browse(company)
            exist_count = self.with_company(company_id).search_count([('name', '=', order_name)])
            if exist_count > 0:
                return f"Sale Order {order_name} already exists."

            partner_ref = vals.pop('customer_ref')
            if not partner_ref:
                return 'partner_ref is missing'

            partner_id = self.env['res.partner'].with_company(company_id).search([('ref', '=', partner_ref)], limit=1)
            if not partner_id:
                partner_id = self.env['res.partner'].with_company(company_id).create([{
                    'name': partner_ref,
                    'ref': partner_ref,
                    'is_company': True,
                }])
                _logger.info(f"Created new partner with ref: {partner_ref}")

            vals['partner_id'] = partner_id.id

            tax_code = vals.get('other_for_mapping', {}).get('tax', '')
            tax_id = self._get_api_tax(tax_code, company_id)

            order_line_1 = vals.pop('order_lines')
            order_line = []
            for line in order_line_1:
                product_code = line.pop('product_code')
                # product_name = line.get('name')
                is_non_stock = line.pop('is_non_stock', False)

                if is_non_stock:
                    product_id = self.env['product.product'].with_company(company_id).search([('name', '=', product_code)], limit=1)
                    if not product_id:
                        _logger.warning(f"Product with name {product_code} not found, skipping line.")
                        continue
                else:
                    product_id = self.env['product.product'].with_company(company_id).search([('default_code', '=', product_code)], limit=1)
                    if not product_id:
                        _logger.warning(f"Product with code {product_code} not found, skipping line.")
                        continue

                line['product_id'] = product_id.id
                line['tax_id'] = [(4, tax_id, 0)] if tax_id else []
                order_line.append((0, 0, line))

            if len(order_line) == 0:
                return '%s: no valid products in order lines' % vals.get('name', 'Unknown Order')

            vals['order_line'] = order_line

            vals['quotation_type'] = 'order_processing'
            additional_for_mapping = vals.pop('other_for_mapping', {})
            
            # map so_status
            status_name = additional_for_mapping['so_status']
            status_rec = self.env['so.status'].search([('name', '=', status_name)], limit=1)
            vals['so_status'] = status_rec.id if status_rec else False

            # map so_price_category and so_price_instruction
            price_category = additional_for_mapping['so_price_category']
            price_instruction = additional_for_mapping['so_price_instruction']
            if price_instruction == 'nan':
                so_price_cat = self.env['so.price.category'].with_company(company_id).search([('name', '=', price_category)], limit=1)
                vals['so_price_category'] = so_price_cat.id if so_price_cat else False
            else:
                so_price_cat = self.env['so.price.category'].with_company(company_id).search([('name', '=', 'Others')], limit=1)
                vals['so_price_category'] = so_price_cat.id if so_price_cat else False
                vals['please_indicate'] = price_instruction

            # map cs_note
            cs_note = additional_for_mapping['cs_note']
            if cs_note != 'nan':
                vals['cs_note'] = cs_note
            else:
                vals['cs_note'] = False

            # map project
            project_val = additional_for_mapping['project']
            if project_val != 'nan':
                vals['project'] = project_val
            else:
                vals['project'] = False

            # map incoterm and incoterm_location
            incoterm = additional_for_mapping['incoterm']
            incoterm_id = self.env['account.incoterms'].search([('name', '=', incoterm)], limit=1)
            vals['incoterm'] = incoterm_id.id if incoterm_id else False

            incoterm_location = additional_for_mapping['incoterm_location']
            if incoterm_location != 'nan':
                vals['incoterm_location'] = incoterm_location
            else:
                vals['incoterm_location'] = False

            please_indicate = additional_for_mapping['please_indicate']
            if please_indicate != 'nan':
                vals['please_indicate'] = please_indicate
            else:
                vals['please_indicate'] = '--'

            #map currency
            company_id = vals.get('company_id')
            company = self.env['res.company'].browse(company_id)
            currency = additional_for_mapping['currency_id']

            if not currency or currency.strip().lower() == 'nan':
                currency = False

            if currency:
                currency_rec = self.env['res.currency'].search([('name', '=', currency)], limit=1)
                if currency_rec:
                    pricelist = self.env['product.pricelist'].with_company(company_id).search([
                        ('currency_id', '=', currency_rec.id),('company_id','=',company.id)
                    ], limit=1)
                    if pricelist:
                        vals['pricelist_id'] = pricelist.id
                    else:
                        vals['pricelist_id'] = self.env.user.property_product_pricelist.id
                else:
                    vals['pricelist_id'] = self.env.user.property_product_pricelist.id
            else:
                vals['pricelist_id'] = self.env.user.property_product_pricelist.id

            order_id = self.with_company(company_id).create(vals)

            order_id.message_post(body=f"Additional Info for Mapping: {additional_for_mapping}")
            order_id.action_confirm_no_workorder()
            
            # Cancel the auto-created picking (will be created separately during migration)
            if order_id.picking_ids:
                for picking in order_id.picking_ids:
                    picking.action_cancel()
            
            return order_id.id

        except Exception as e:
            _logger.error(f"Error creating sale order: {str(e)}")
            return f"Error: {str(e)}"

    @api.model
    def _get_api_tax(self, tax_code, company_id):
        """
        Helper method to retrieve tax based on tax code.
        """

        tax_map = {
            'outscope~|~0': 11,     # 0% ZR
            'stdrated~|~7': 12,     # 7% SR
            'stdrated~|~8': 3,      # 8% SR
            'stdrated~|~9': 4,      # 9% SR
        }
        tax = tax_map.get(tax_code, False)

        # if 'stdrated' in tax_code:
        #     tx_domain = [('name', '=', '9% SR'), ('company_id', '=', company_id.id)]
        #     tax_id = self.env['account.tax'].search(tx_domain, limit=1)
        #     return tax_id
        return tax

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    old_sale_order_line = fields.Integer(string='Old Sale Order Line ID')
