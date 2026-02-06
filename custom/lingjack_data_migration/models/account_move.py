from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    old_move = fields.Integer(string='Old Move ID')

    @api.model
    def api_create_vendor_bills(self, vals):
        try:
            bill_number = vals.get('ref')
            if not bill_number:
                return "Missing bill number"

            move = self.search([
                ('ref', '=', bill_number),
                ('move_type', '=', 'in_invoice')
            ], limit=1)
            if move:
                return f"Vendor Bill {bill_number} already exists"

            vendor_ref = vals.get('partner_id')
            vendor = self.env['res.partner'].search([('ref', '=', vendor_ref),
                                                     ('company_id', '=', vals.get('company_id', 0)),
                                                     ('supplier_rank', '>', 0)], limit=1)

            if not vendor:
                vendor = self.env['res.partner'].create({
                    'name': vendor_ref,
                    'ref': vendor_ref,
                    'supplier_rank': 1,
                    'is_company': True,
                })

            vals['partner_id'] = vendor.id
            bill_lines = []

            # # Batch fetch all products to avoid N+1 query problem
            # product_codes = [
            #     line.get('product_code')
            #     for line in vals.get('bill_line_data', [])
            #     if line.get('product_code')
            # ]
            #
            # products_map = {}
            # if product_codes:
            #     products = self.env['product.product'].search([
            #         ('default_code', 'in', product_codes)
            #     ])
            #     products_map = {p.default_code: p for p in products}
            #
            # # Batch fetch all purchase orders to avoid N+1 query problem
            # po_names = [
            #     line.get('purchase_order')
            #     for line in vals.get('bill_line_data', [])
            #     if line.get('purchase_order')
            # ]
            #
            # pos_map = {}
            # if po_names:
            #     pos = self.env['purchase.order'].search([
            #         ('name', 'in', po_names)
            #     ])
            #     pos_map = {po.name: po for po in pos}

            # Batch fetch all purchase order lines by old_purchase_order_line to avoid N+1 query problem
            old_po_line_ids = [
                int(line.get('purchase_line_id'))
                for line in vals.get('bill_line_data', [])
                if line.get('purchase_line_id')
            ]

            po_lines_map = {}
            if old_po_line_ids:
                po_line_ids = self.env['purchase.order.line'].search([('old_purchase_order_line', 'in', old_po_line_ids)])
                po_lines_map = {pol.old_purchase_order_line: pol for pol in po_line_ids}

            # Process bill lines using the pre-fetched maps
            for line in vals.get('bill_line_data', []):
                purchase_line_id = line.get('purchase_line_id')
                if not purchase_line_id:
                    return f'One line has been sent without a purchase line - unable to create the vendor bill'

                po_line_id = po_lines_map.get(int(purchase_line_id))
                if not po_line_id:
                    return f'Purchase Line {purchase_line_id} does not exist in odoo'

                name = line.get('name')
                qty = line.get('quantity', 0)
                price = line.get('price_unit', 0.0)
                tax_code = line.get('tax_code', '')
                if tax_code == 'overseapur~|~0':
                    tax_id = 43
                elif tax_code =='stdrated~|~9':
                    tax_id = 22
                elif tax_code =='zerorated~|~0':
                    tax_id = 42
                else:
                    tax_id = 0

                line_vals = {
                    'product_id': po_line_id.product_id.id,
                    'name': name or po_line_id.name,
                    'quantity': qty,
                    'price_unit': price,
                    'analytic_distribution': line.get('analytic_distribution') or {},
                    'tax_ids': tax_id and [(4, tax_id, 0)] or False,
                }
                bill_lines.append((0, 0, line_vals))

                # product_code = line.get('product_code')
                # qty = line.get('quantity', 0)
                # price = line.get('price_unit', 0.0)
                # name = line.get('name')
                #
                # purchase_order = line.get('purchase_order')
                #
                # # Dictionary lookup - no database query needed
                # product = products_map.get(product_code)
                # if not product:
                #     continue
                #
                # po_line = False
                # if purchase_line_id:
                #     # Dictionary lookup by old_purchase_order_line - no database query needed
                #     po_line = po_lines_map.get(int(purchase_line_id))
                #
                # if not po_line and purchase_order:
                #     # Dictionary lookup - no database query needed
                #     po = pos_map.get(purchase_order)
                #     if po:
                #         po_line = po.order_line.filtered(
                #             lambda l: l.product_id.id == product.id
                #         )[:1]
                #
                # line_vals = {
                #     'product_id': product.id,
                #     'name': name or product.display_name,
                #     'quantity': qty,
                #     'price_unit': price,
                #     'analytic_distribution': line.get('analytic_distribution') or {},
                # }
                #
                # if po_line:
                #     line_vals['purchase_line_id'] = po_line.id

                # bill_lines.append((0, 0, line_vals))

            if not bill_lines:
                return f"No valid lines for Vendor Bill {bill_number}"

            vals.pop('bill_line_data', None)
            vals['invoice_line_ids'] = bill_lines
            vals['move_type'] = 'in_invoice'
            vals['state'] = 'draft'

            bill = self.create(vals)
            return bill.id

        except Exception as e:
            return f"Error: {str(e)}"

    @api.model
    def api_create_invoice(self, vals):
        """Create invoice linked to sale order lines and log mismatches."""

        tax_map = {
            'outscope~|~0': 11,  # 0% ZR
            'stdrated~|~7': 12,  # 7% SR
            'stdrated~|~8': 3,  # 8% SR
            'stdrated~|~9': 4,  # 9% SR
        }

        try:
            log_entries = []
            invoice_lines = []
            invoice_number = vals.get('ref')
            if not invoice_number:
                return "Missing invoice number"

            # company
            company = vals.get('company_id')
            company_id = self.env['res.company'].browse(company)

            # Avoid duplicates
            if self.with_company(company_id).search_count([('ref', '=', invoice_number)]):
                return f"Invoice {invoice_number} already exists."

            partner_ref = vals.get('partner_id')
            if not partner_ref:
                return f"{invoice_number}: Missing partner_ref"

            partner = self.env['res.partner'].with_company(company_id).search([('ref', '=', partner_ref)], limit=1)
            if not partner:
                # partner = self.env['res.partner'].create({
                #     'name': partner_ref,
                #     'ref': partner_ref,
                #     'is_company': True,
                #     'customer_rank': 1,
                # })
                return f"{invoice_number}: Missing partner"
            vals['partner_id'] = partner.id

            attention_name = vals.get('attention_id')
            if attention_name:
                attention_partner = self.env['res.partner'].with_company(company_id).search([
                    ('name', '=', attention_name),
                    ('parent_id', '=', partner.id),
                    ('type', '=', 'contact')
                ], limit=1)
                # if not attention_partner:
                    # attention_partner = self.env['res.partner'].create({
                    #     'name': attention_name,
                    #     'parent_id': partner.id,
                    #     'type': 'contact',
                    # })
                    # return f"{invoice_number}: Missing attention partner"
                vals['attention_id'] = attention_partner and  attention_partner.id or False
            else:
                vals['attention_id'] = False

            # Batch fetch all sale order lines to avoid N+1 query problem
            old_sale_line_ids = [
                int(line.get('old_sale_line'))
                for line in vals.get('invoice_line_data', [])
                if line.get('old_sale_line')
            ]

            # Single database query to fetch all required sale lines
            sale_lines_map = {}
            if old_sale_line_ids:
                sale_lines = self.env['sale.order.line'].with_company(company_id).search([
                    ('old_sale_order_line', 'in', old_sale_line_ids)
                ])
                # Create dictionary mapping for O(1) lookup
                sale_lines_map = {sl.old_sale_order_line: sl for sl in sale_lines}

            # Process invoice lines using the pre-fetched map
            for line in vals.get('invoice_line_data', []):
                old_sale_line = line.get('old_sale_line')
                sale_line = False

                if old_sale_line:
                    # Dictionary lookup - no database query needed
                    sale_line = sale_lines_map.get(int(old_sale_line))

                if sale_line:
                    account_number = line.get('account_id')
                    account_id = self.env['account.account'].with_company(company_id).search([('code', '=', account_number)], limit=1)
                    tax = tax_map.get(line.get('tax_code'))
                    line_vals = {
                        'product_id': sale_line.product_id.id,
                        'account_id': account_id and account_id.id,
                        'name': sale_line.name,
                        'quantity': line.get('quantity', 1),
                        'price_unit': line.get('price_unit', 0.0),
                        'old_move_line': line.get('old_move_line', 0),
                        'sale_line_ids': [(6, 0, [sale_line.id])],
                        'tax_ids': tax and [(6, 0 , [tax])]
                    }
                    if not account_id:
                        line_vals.pop('account_id')
                        return f'unable to create invoice: account missing: {account_number}'

                    invoice_lines.append((0, 0, line_vals))

                else:
                    return f'unable to create invoice: no sale line for {sale_line}'

            if not invoice_lines:
                return f" No valid lines for invoice {invoice_number}"

            vals.pop('invoice_line_data', None)
            vals['invoice_line_ids'] = invoice_lines
            vals.setdefault('move_type', 'out_invoice')
            vals.setdefault('state', 'draft')

            invoice = self.create(vals)

            # Log mismatches
            if log_entries:
                self.env['ir.logging'].create({
                    'name': f"Invoice {invoice.name} Mismatch Log",
                    'type': 'server',
                    'level': 'WARNING',
                    'dbname': self._cr.dbname,
                    'message': str(log_entries),
                    'path': 'account.move.api_create_invoice',
                    'func': 'api_create_invoice',
                    'line': '0',
                })

            _logger.info(f"Created Invoice {invoice.name} ({len(invoice_lines)} lines)")
            return invoice.id

        except Exception as e:
            _logger.error(f"Error creating invoice: {str(e)}")
            return f"Error: {str(e)}"

    @api.model
    def api_add_downpayment_invoice(self, company, vals):
        domain = [('name', '=', vals['invoice.number'])]
        invoice_id = self.with_company(company).search(domain, limit=1)
        if not invoice_id:
            return f"Invoice number {invoice_id} not found"
        if invoice_id.state != 'draft':
            return f"Invoice number {invoice_id} not draft"

        account = vals.get('account.code')
        account_id = self.env['account.account'].with_company(company).search([('code', '=', account)], limit=1)
        if not account_id:
            return f'Account code {account} not found'

        tax_code = vals.get('tax.code')
        if tax_code == 'stdrated~|~9':
            tax_id = 4
        elif tax_code == 'zerorated~|~0':
            tax_id = 11
        else:
            tax_id = 0
        line_vals = {
            'name': vals['invoice.write_off.number'],
            'account_id': account_id.id,
            'display_type': 'product',
            'quantity': vals['qty'],
            'price_unit': vals['amount'],
            'tax_ids': tax_id and [(4, tax_id, 0)] or False,
        }

        invoice_id.write({'invoice_line_ids': [(0, 0, line_vals)]})
        return f"Invoice number {invoice_id} written off"


class AccountMoveLine(models.Model):
        _inherit = 'account.move.line'

        old_move_line = fields.Integer(string='Old Move Line ID')

