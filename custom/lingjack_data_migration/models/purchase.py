from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    old_purchase_order = fields.Integer(string='Old Purchase Order ID')


    @api.model
    def api_create_purchase_order(self, vals):
        try:
            order_name = vals.get('name', 'Unknown Order')
            company = vals.get('company_id')
            vals['purchaser_type'] = 'non_procurement'
            company_id = self.env['res.company'].browse(company)

            existing_po = self.with_company(company_id).search([('name', '=', order_name)], limit=1)
            if existing_po:
                return f"Purchase Order {order_name} already exists."

            partner_ref = vals['partner_ref']
            if not partner_ref:
                return f"{order_name}: Missing partner_ref"

            partner_id = self.env['res.partner'].with_company(company_id).search([('ref', '=', partner_ref)], limit=1)
            if not partner_id:
                return 'Partner Ref cannot be found'

            vals['partner_id'] = partner_id.id

            order_lines = vals.pop('order_lines', [])
            valid_lines = []
            for line in order_lines:
                is_non_stock = line.pop('is_non_stock', False)
                product_code = line.pop('product_code', None)
                if is_non_stock:
                    product_id = self.env['product.product'].with_company(company_id).search(
                        [('name', '=', product_code)], limit=1)
                    if not product_id:
                        _logger.warning(f"Product with name {product_code} not found, skipping line.")
                        continue
                else:
                    product_id = self.env['product.product'].with_company(company_id).search([('default_code', '=', product_code)], limit=1)
                    if not product_id:
                        _logger.warning(f"Product with code {product_code} not found, skipping line.")
                        continue

                tax_map = {
                    "stdrated~|~9": 22,     # 9% TX,
                    "overseapur~|~0": 43,   # out-of-scope purchase
                    "outscope~|~0": 43,     # out-of-scope purchase
                    "zerorated~|~0": 42     # Zero rated purchase
                }
                tax = tax_map.get(line.get("tax", ""))
                tax_ids = tax and [(6, 0, [tax])] or False

                description = (line.get("product_description", "") + " " + line.get("product_remarks", "")).strip()

                valid_lines.append((0, 0, {
                    'product_id': product_id.id,
                    'name': description,
                    'product_qty': line.get('product_qty', 0),
                    'price_unit': line.get("unit_price", 0),
                    'taxes_id': tax_ids,
                    'old_purchase_order_line': line.get('old_purchase_order_line')
                }))

            vals['order_line'] = valid_lines

            vals.setdefault('state', 'draft')
            vals.setdefault('company_id', self.env.company.id)
            if vals.get('currency_id'):
                currency_id = self.env['res.currency'].search([('name','=',vals.get('currency_id'))])
                if currency_id:
                    vals['currency_id'] = currency_id.id
                else:
                    vals['currency_id'] = self.env.company.currency_id.id

            date_str = vals.get('date_order')
            if isinstance(date_str, str) and '.' in date_str:
                vals['date_order'] = date_str.split('.')[0]

            order = self.create(vals)
            _logger.info(f" Created visible PO: {order.name} (id {order.id}) for company {order.company_id.name}")
            order.with_context(merge_line=False).button_confirm()
            order.sudo().write({'date_approve':vals.get('date_order')})
            return order.id

        except Exception as e:
            _logger.error(f"Error creating purchase order: {str(e)}")
            return f" Error: {str(e)}"


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    old_purchase_order_line = fields.Integer(string='Old Purchase Order Line ID')
