from odoo import models, api, fields,_
from odoo.exceptions import UserError, ValidationError
import json
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import get_lang



class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    attention_id = fields.Many2one('res.partner', string='Attn')
    project_ref = fields.Char(string='Project Reference')

    total_in_home_currency = fields.Monetary(
        string='Total In Home Currency',
        currency_field='company_currency_id',
        compute='_compute_total_in_home_currency',
        store=True,
    )

    company_currency_id = fields.Many2one(
        'res.currency', string="Company Currency",
        related='company_id.currency_id', readonly=True
    )

    revision_id = fields.Many2one('revision.list', string="Revision")

    purchaser_type = fields.Selection([('procurement', 'Procurement'),('non_procurement', 'Non-Procurement')], string="Purchaser Type", default='non_procurement')
    purchase_type_id = fields.Many2one('purchase.type',string='Purchase Type')

    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        super(PurchaseOrder, self)._onchange_requisition_id()
        if self.requisition_id:
            self.purchaser_type = self.requisition_id.purchaser_type

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            purchaser_type = (vals.get('purchaser_type') or self.default_get(['purchaser_type']).get('purchaser_type'))
        if vals.get('name', 'New') == 'New':
            if purchaser_type == 'non_procurement':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order.non.procurement') or 'New'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order') or 'New'
        return super(PurchaseOrder, self).create(vals)


    @api.depends('order_line.price_unit', 'order_line.product_qty', 'order_line.discount', 'currency_id', 'company_id',
                 'date_order')
    def _compute_total_in_home_currency(self):
        for order in self:
            total = 0.0
            for line in order.order_line:
                line_total = line.price_unit * line.product_qty
                discount = line.discount or 0.0
                discount_amount = line_total * (discount / 100.0)
                subtotal = line_total - discount_amount
                total += subtotal

            order.total_in_home_currency = order.currency_id._convert(
                total,
                order.company_id.currency_id,
                order.company_id,
                order.date_order or fields.Date.today()
            ) if order.currency_id and order.company_id else 0.0

    def merge_duplicate_lines(self):
        for order in self:
            line_map = {}
            lines_to_remove = self.env['purchase.order.line']
            for line in order.order_line:
                key = ((line.name or '').strip(), line.date_planned, round(line.price_unit, 2))
                if key in line_map:
                    existing = line_map[key]
                    existing.product_qty += line.product_qty
                    existing.price_unit = line.price_unit
                    lines_to_remove |= line
                else:
                    line_map[key] = line
            lines_to_remove.unlink()

    def button_confirm(self):
        merge_line = self.env.context.get('merge_line', True)   # Provide a mechanism to by-pass this custom function
        if merge_line:
            self.merge_duplicate_lines()
        return super().button_confirm()

    def _prepare_invoice(self):
        res = super(PurchaseOrder, self)._prepare_invoice()
        res.update({'purchase_type_id': self.purchase_type_id.id,
                    'purchaser_type': self.purchaser_type,
                    })
        return res

class Purpose(models.Model):
    _name = 'purpose.purpose'
    _description = 'purpose'

    name = fields.Char(string='Purpose ', required=True)


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    purpose = fields.Selection([
        ('production_use', 'Production Use'),
        ('rnd', 'R&D'),
        ('stock', 'Stock')
    ], string="Purpose")
    expected_date = fields.Date(string='Expected Date')

    discount = fields.Float(string='Discount (%)')
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)

    qty_to_order = fields.Float(string="Qty to Order",compute="_compute_qty_to_order",store=True,)
    rfq_po_qty = fields.Float(string="RFQ/PO Qty", store=True, compute='_compute_rfq_po_qty')

    @api.depends('product_qty', 'price_unit', 'discount')
    def _compute_subtotal(self):
        for line in self:
            price = line.product_qty * line.price_unit
            discount_amount = price * (line.discount / 100.0)
            line.subtotal = price - discount_amount

    @api.depends('product_qty', 'qty_ordered','rfq_po_qty')
    def _compute_qty_to_order(self):
        for line in self:
            line.qty_to_order = line.product_qty - line.rfq_po_qty



    @api.depends('requisition_id.purchase_ids.state', 'requisition_id.purchase_ids.order_line.product_qty')
    def _compute_rfq_po_qty(self):
        for line in self:
            total_rfq_po_qty = 0.0
            for po in line.requisition_id.purchase_ids.filtered(lambda purchase_order: purchase_order.state not in ['cancel']):
                for po_line in po.order_line.filtered(lambda order_line: order_line.product_id == line.product_id):
                    if po_line.product_uom != line.product_uom_id:
                        total_rfq_po_qty += po_line.product_uom._compute_quantity(po_line.product_qty, line.product_uom_id)
                    else:
                        total_rfq_po_qty += po_line.product_qty
            line.rfq_po_qty = total_rfq_po_qty

    def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
        self.ensure_one()

        if self.qty_to_order <= 0:
            return {}

        res = super()._prepare_purchase_order_line(name, product_qty, price_unit, taxes_ids)
        res['discount'] = self.discount or 0.0
        qty = self.qty_to_order
        if self.product_uom_id != self.product_id.uom_po_id:
            qty = self.product_uom_id._compute_quantity(qty, self.product_id.uom_po_id)
        res['product_qty'] = qty

        if self.expected_date:
            res['date_planned'] = self.expected_date

        return res


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    currency_id = fields.Many2one(
        'res.currency', string="Currency", required=True,
        default=lambda self: self.env.company.currency_id
    )
    total_in_currency = fields.Monetary(
        string='Total in Currency',
        currency_field='currency_id',
        compute='_compute_totals', store=True,

    )
    total_in_home_currency = fields.Monetary(
        string='Total In Home Currency',
        currency_field='company_currency_id',
        compute='_compute_totals', store=True,
    )
    company_currency_id = fields.Many2one(
        'res.currency', string="Company Currency",
        related='company_id.currency_id', readonly=True
    )
    purpose_id = fields.Many2one('purpose.purpose', string="Purpose")

    purchase_type_id = fields.Many2one('purchase.type', string="Purchase Type")

    purchaser_type = fields.Selection([('procurement', 'Procurement'),('non_procurement', 'Non-Procurement')], string="Purchaser Type", default='procurement')



    def action_confirm(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError(
                _("You cannot confirm agreement '%s' because it does not contain any product lines.")
                % self.name
            )

        if self.requisition_type == 'blanket_order':
            for line in self.line_ids:
                if line.product_qty <= 0:
                    raise UserError(
                        _("You cannot confirm a blanket order with lines missing a quantity.")
                    )
                line._create_supplier_info()
        self.state = 'confirmed'

    @api.depends('line_ids.subtotal', 'currency_id', 'company_id')
    def _compute_totals(self):
        for requisition in self:
            total = sum(requisition.line_ids.mapped('subtotal'))
            requisition.total_in_currency = total

            if requisition.currency_id and requisition.company_id:
                requisition.total_in_home_currency = requisition.currency_id._convert(
                    total,
                    requisition.company_id.currency_id,
                    requisition.company_id,
                    requisition.date_start or fields.Date.today()
                )
            else:
                requisition.total_in_home_currency = 0.0

    def _auto_close_confirmed_requisitions(self):
        confirmed_reqs = self.search([('state', '=', 'confirmed')])
        for requisition in confirmed_reqs:
            rfqs_still_open = requisition.purchase_ids.filtered(lambda p: p.state in ['draft', 'sent'])
            if rfqs_still_open:
                continue
            all_qty_done = all(
                line.qty_to_order <= 0 for line in requisition.line_ids
            )
            if all_qty_done:
                requisition.action_done()

    @api.onchange('vendor_id')
    def _onchange_vendor(self):
        if not self.vendor_id:
            return

        return super(PurchaseRequisition, self)._onchange_vendor()


class PurchaseType(models.Model):
    _name = 'purchase.type'
    _description = 'purchase type'

    name = fields.Char(string='Purchase Type ', required=True)
    company_ids = fields.Many2many('res.company', string='Companies')

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_id_domain = fields.Binary("Product Id Domain", compute="_compute_product_id_domain")
    sale_order_ids = fields.Many2many('sale.order',string='Sales Orders')

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move)
        res.update({'sale_order_ids': self.sale_order_ids})
        return res

    @api.depends('order_id.purchaser_type', 'company_id')
    def _compute_product_id_domain(self):
        for line in self:
            domain = [
                ('purchase_ok', '=', True),
                '|',
                ('company_id', '=', False),
                ('company_id', 'parent_of', line.company_id.id),
            ]
            if line.order_id.purchaser_type == 'non_procurement':
                domain.append(('type', '=', 'service'))
            line.product_id_domain = json.dumps(domain)

    def write(self, vals):
        name_val = vals.get('name')
        if name_val:
            lines = name_val.splitlines()
            if lines and lines[0].strip().startswith('['):
                lines = lines[1:]
            clear_name = '\n'.join(lines).strip()
            vals['name'] = clear_name

        res = super().write(vals)
        return res

    def _compute_price_unit_and_date_planned_and_name(self):
        po_lines_without_requisition = self.env['purchase.order.line']

        for pol in self:
            if pol.product_id.id not in pol.order_id.requisition_id.line_ids.product_id.ids:
                po_lines_without_requisition |= pol
                continue

            passed_rfq_line = []
            for line in pol.order_id.requisition_id.line_ids:
                if line.product_id == pol.product_id and line.product_qty == line.id not in passed_rfq_line:
                    passed_rfq_line.append(line.id)

                    pol.price_unit = line.product_uom_id._compute_price(line.price_unit, pol.product_uom)
                    partner = pol.order_id.partner_id or pol.order_id.requisition_id.vendor_id
                    params = {'order_id': pol.order_id}

                    seller = pol.product_id._select_seller(
                        partner_id=partner,
                        quantity=pol.product_qty,
                        date=pol.order_id.date_order and pol.order_id.date_order.date(),
                        uom_id=line.product_uom_id,
                        params=params
                    )

                    if not pol.date_planned:
                        pol.date_planned = pol._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

                    product_ctx = {'seller_id': seller.id, 'lang': get_lang(pol.env, partner.lang).code}
                    name = pol._get_product_purchase_description(pol.product_id.with_context(product_ctx))
                    if line.product_description_variants:
                        name += '\n' + line.product_description_variants

                    pol.name = name
                    break

        super(PurchaseOrderLine, po_lines_without_requisition)._compute_price_unit_and_date_planned_and_name()

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()

        tmpl = product_lang.product_tmpl_id

        # Dynamic Fields
        default_code = product_lang.default_code
        version = tmpl.version_id.name
        dwg_no = tmpl.dwg_no
        brand = tmpl.brand_id.name or ''
        model = tmpl.product_model_id.name or ''
        name = tmpl.name
        desc = tmpl.product_description
        remarks = tmpl.special_remarks
        purchase = tmpl.description_purchase

        seller_id = product_lang.env.context.get('seller_id')
        vendor_info = self.env['product.supplierinfo'].browse(seller_id) if seller_id else None
        product_code = vendor_info.product_code if vendor_info and vendor_info.product_code else ''

        lines = []

        line1 = " ".join(filter(None, [
            f"Com No {default_code}" if default_code else "",
            f"Rev {version}" if version else "",
            f"(Dwg No {dwg_no})" if dwg_no else "",
            f" {product_code}" if product_code else "",
        ])).strip()
        if line1:
            lines.append(line1)

        name_prefix = " ".join(filter(None, [brand, model, name]))
        line2 = " - ".join(filter(None, [name_prefix, desc]))
        if line2:
            lines.append(line2)
        if purchase:
            lines.append(purchase)
        if remarks:
            lines.append(remarks)
        full_description = "\n".join(lines).strip()

        return full_description


class PurchaseAdvancePaymentInv(models.TransientModel):
    _inherit = "purchase.advance.payment.inv"

    def _prepare_deposit_val(self, order, po_line, amount):
        vals = super(PurchaseAdvancePaymentInv, self)._prepare_deposit_val(order, po_line, amount)
        vals.update({
            "purchase_type_id": order.purchase_type_id.id,
        })
        return vals


