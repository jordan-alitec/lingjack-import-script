from odoo import models, fields,api,_
from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import float_round
from datetime import timedelta



class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_to_id = fields.Many2one('delivery.to', string='Delivery To')
    project = fields.Char(string='Customer Project')

    sale_type_id = fields.Many2one('sale.type', string="Sale Type")
    quote_type_id = fields.Many2one('type.code', string="Type of Quote")

    sale_date = fields.Date(string="Date")
    person_incharge_id = fields.Many2one('hr.employee', string="Person Incharge")
    remarks = fields.Html(string="Remarks")

    type_order_id = fields.Many2one('type.order', string="Type Of Order")

    attention_id = fields.Many2one('res.partner', string='Attention')
    ship_to_attention_ids = fields.Many2many('res.partner','ship_to_attention_rel','record_id','partner_id',string='Ship To Attention')
    quotation_type = fields.Selection([
        ('sales_quote', 'Sales Quote'),
        ('order_processing', 'Order Processing'), ], string="Quotation Type")

    third_party_quot_id = fields.Many2one('res.partner', string='Third Party Quotation')

    revision_id = fields.Many2one('revision.list', string="Revision")

    approve = fields.Boolean(string='Approved', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)

    customer_part_id = fields.Many2one('customer.part.number', string='Customer Part Number Template')

    so_status = fields.Many2one('so.status', string="SO Status")
    so_price_category = fields.Many2one('so.price.category', string="SO Price Category")
    please_indicate = fields.Text(string="Please Indicate")
    cs_note = fields.Text(string="CS-Note")

    amount_home_currency = fields.Monetary(
        string="Amount in Home Currency",
        compute="_compute_amount_home_currency",
        currency_field='company_currency_id',
        store=True
    )

    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string="Company Currency",
        readonly=True
    )
    cs_in_charge_id = fields.Many2one(comodel_name='res.users', string='CS-In Charge')

    sales_comment = fields.Text(string="Sales Comment")
    finance_comment = fields.Text(string="Finance Comment")
    management_comment = fields.Text(string="Management Comment")

    apply_manual_payment_terms = fields.Boolean(string="Apply Manual Payment Terms" )
    manual_payment_terms = fields.Char(string="Manual Payment Terms")
    currency_pricelist_id = fields.Many2one(
        related='pricelist_id.currency_id',
        string="Pricelist Currency",
        store=False,
    )

    partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Recipient Bank',
        compute='_compute_partner_bank_id', store=True, readonly=False,
        help="Bank Account Number to which the payment will be made. "
             "A Company bank account if this is a Customer Invoice, "
             "otherwise a Partner bank account number.",
        check_company=True,
        tracking=True,
        ondelete='restrict',
        domain="[('currency_id', '=', currency_pricelist_id)]"
    )
    purchase_requisition_ids = fields.Many2many('purchase.requisition', string='Purchase Requisitions')

    delivery = fields.Text(string="Delivery")
    order_warranty_period = fields.Float(string="Order Warranty Period (Days)",digits=(10, 0),)


    @api.depends('company_id')
    def _compute_partner_bank_id(self):
        for order in self:
            # Get the bank account from the partner in the order, trusted first
            bank_ids = order.company_id.bank_ids.filtered(
                lambda bank: not bank.company_id or bank.company_id == order.company_id
            )
            order.partner_bank_id = bank_ids[:1]



    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['cs_in_charge_id'] = self.cs_in_charge_id.id
        invoice_vals['project'] = self.project
        invoice_vals['attention_id'] = self.attention_id.id
        invoice_vals['manual_payment_terms'] = self.manual_payment_terms

        return invoice_vals

    @api.depends('amount_untaxed', 'currency_id', 'company_currency_id', 'date_order')
    def _compute_amount_home_currency(self):
        for order in self:
            order.amount_home_currency = 0.0
            if order.currency_id and order.company_currency_id and order.date_order:
                rates = order.currency_id._get_rates(order.company_id, order.date_order)
                rate = rates.get(order.currency_id.id)
                if rate:
                    inverse_rate = 1 / rate if rate != 0 else 0
                    order.amount_home_currency = float_round(
                        order.amount_untaxed * inverse_rate,
                        precision_digits=order.company_currency_id.decimal_places or 2
                    )
    def action_approve(self):
        for picking in self:
            picking.write({
                'approve': True,
                'approved_by': self.env.user.id,
                'approved_on': datetime.now()
            })

    def action_confirm(self):
        is_export_control = any(
            line.product_id.product_tmpl_id.is_export_control for line in self.order_line
        )

        if is_export_control and not self.env.context.get('no_open_export_wizard'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'confirm.export.control.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_sale_order_id': self.id,
                }
            }
        return super(SaleOrder, self).action_confirm()

    def action_apply_warranty(self):
        for order in self:
            if order.order_warranty_period:
                for line in order.order_line:
                    line.warranty_period = order.order_warranty_period
            else:
                raise UserError(_("Please set Order Warranty Period before applying."))

    def action_apply_customer_part(self):
        for order in self:
            customer_part_template = order.customer_part_id

            for line in order.order_line:
                matching_line = customer_part_template.part_line_ids.filtered(
                    lambda l: l.product_id.id == line.product_id.id
                )

                if customer_part_template.replace_with_customer_description:
                    if matching_line and matching_line[0].customer_description:
                        ## Append the extra description to the customer description
                        line.name = matching_line[0].customer_description + line._extra_description_sale_line()
                else:
                    line.name = line._get_sale_order_line_multiline_description_sale()

class SaleType(models.Model):
    _name = 'sale.type'
    _description = 'Sale Type'

    name = fields.Char(string='Visit Purpose', required=True)
    is_service = fields.Boolean(string='Is Service', default=False)

class TypeCode(models.Model):
    _name = 'type.code'
    _description = 'Sale Type'

    name = fields.Char(string='Visit Purpose', required=True)

class TypeOfOrder(models.Model):
    _name = 'type.order'
    _description = 'Type Of Order'

    name = fields.Char(string='Visit Purpose', required=True)

class RevisionList(models.Model):
    _name = 'revision.list'
    _description = 'Revision List'

    name = fields.Char(string='Revision', required=True)

class DeliveryTo(models.Model):
    _name = 'delivery.to'
    _description = 'delivery TO'

    name = fields.Char(string='Delivery To ', required=True)


class SOStatus(models.Model):
    _name = 'so.status'
    _description = 'SO Status'

    name = fields.Char(string='Status', required=True)

class SOPriceCategory(models.Model):
    _name = 'so.price.category'
    _description = 'SO Price Category'

    name = fields.Char(string='Category', required=True)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    commitment_date = fields.Datetime("Delivery Date")
    delivery = fields.Text(string="Delivery")
    warranty_period = fields.Float(string="Warranty Period (Days)",digits=(10, 0))
    remarks = fields.Text(string="Remarks")

    @api.onchange('product_id')
    def _onchange_product_id_set_warranty(self):
        for line in self:
            if not line.product_id:
                continue

            order = line.order_id
            if order and order.order_warranty_period and order.order_warranty_period > 0:
                line.warranty_period = order.order_warranty_period
            else:
                line.warranty_period = line.product_id.product_tmpl_id.sales_supplier_warranty

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        # has ensure_one already
        if self.commitment_date:
            vals.update(
                {
                    "date_planned": self.commitment_date - timedelta(days=self.order_id.company_id.security_lead),
                    "date_deadline": self.commitment_date,
                }
            )
        return vals

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.name:
            res.update({'name': self.name})
        return res

    def write(self, vals):
        name_val = vals.get('name')
        if name_val:
            lines = name_val.splitlines()
            if lines and lines[0].strip().startswith('['):
                lines = lines[1:]
            clear_name = '\n'.join(lines).strip()
            vals['name'] = clear_name

        res = super().write(vals)
        moves_to_upd = set()
        if "commitment_date" in vals:
            for line in self:
                for move in line.move_ids:
                    if move.state not in ["cancel", "done"]:
                        moves_to_upd.add(move.id)
        if moves_to_upd:
            self.env["stock.move"].browse(moves_to_upd).write(
                {"date_deadline": vals.get("commitment_date")}
            )
        return res

    def _get_sale_order_line_multiline_description_sale(self):
        self.ensure_one()
        product = self.product_id
        order = self.order_id

        # Fields
        default_code = (product.default_code or '').strip()
        version_id = (product.version_id.name or '').strip()
        dwg_no = (product.dwg_no or '').strip()
        brand_id = (product.brand_id.name or '').strip()
        product_model_id = (product.product_model_id.name or '').strip()
        product_name = (product.name or '').strip()
        product_desc = (product.product_description or '').strip()
        quotation_description = (product.description_sale or '').strip()
        special_remarks = (product.special_remarks or '').strip()

        customer_part_no = ''
        customer_description = ''
        if order.customer_part_id:
            matching_line = order.customer_part_id.part_line_ids.filtered(
                lambda l: l.product_id.id == product.id
            )
            if matching_line:
                customer_part_no = (matching_line[0].customer_part_number or '').strip()
                customer_description = (matching_line[0].customer_description or '').strip()

        if order.customer_part_id and order.customer_part_id.replace_with_customer_description and customer_description:
            return customer_description + self._extra_description_sale_line()

        custom_desc_parts = []
        if default_code:
            custom_desc_parts.append(_("Com %s") % default_code)
        if version_id:
            custom_desc_parts.append(_("Rev %s") % version_id)
        if dwg_no:
            custom_desc_parts.append(_("(Dwg No %s)") % dwg_no)
        if customer_part_no:
            custom_desc_parts.append(customer_part_no)

        custom_desc = " ".join(custom_desc_parts)

        name_parts = []
        if brand_id:
            name_parts.append(brand_id)
        if product_model_id:
            name_parts.append(product_model_id)
        if product_name:
            name_parts.append(product_name)

        full_product_line = " ".join(name_parts)
        if product_desc:
            product_line = "%s - %s" % (full_product_line, product_desc)
        else:
            product_line = full_product_line

        full_description = "\n".join(filter(None, [
            custom_desc.strip() or None,
            product_line.strip() or None,
            quotation_description.strip() or None,
            special_remarks.strip() or None,
        ]))

        return full_description + self._extra_description_sale_line()


    def _extra_description_sale_line(self):
        '''
        This function is to make sure the description can be append after all other descriptio is generated
        Supposely should use _get_sale_order_line_multiline_description_sale function but we cannot control the super function which to compute first
        '''
        return ''