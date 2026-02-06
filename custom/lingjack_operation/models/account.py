from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import json


class AccountMove(models.Model):
    _inherit = 'account.move'

    person_incharge_id = fields.Many2one('hr.employee', string='Person in Charge')
    shipment_date = fields.Date(string='Date of Shipment')
    forwarder = fields.Many2one('res.partner', string='Forwarder')
    forwarder_contact = fields.Char(string='Forwarder Contact')
    attention_id = fields.Many2one('res.partner',string='Attention')
    port_loading_id = fields.Many2one('port.port', string='Port Of Loading')
    port_discharge_id = fields.Many2one('port.port', string='Port Of Discharge')

    etd_origin = fields.Date(string='ETD Origin')
    eta_destination = fields.Date(string='ETA Destination')

    vessel_name = fields.Char(string='Name of Vessel/Voyage')
    lc_no = fields.Char(string='L/C No')
    consignee_id = fields.Many2one('res.partner',string='Consignee')
    no_of_package = fields.Char(string='No. Of Package')
    seal_no = fields.Char(string='Seal No')
    container_no = fields.Char(string='Container No')
    packaging_gross_weight = fields.Float(string='Packaging Material Gross Weight')
    manual_payment_terms = fields.Char(string="Manual Payment Terms")
    paid = fields.Boolean(string="Paid", tracking=True)
    paid_by_id = fields.Many2one('hr.employee', string="Paid By", tracking=True)
    consignee_contacts_id = fields.Many2one('res.partner', string='Consignee Contact')
    cn_reason_id = fields.Many2one('cn.reason', string='CN Reason')


    sub_total_net_weight = fields.Float(
        string='Sub Total Net Weight',
        compute='_compute_sub_total_net_weight',
        store=True
    )
    net_total = fields.Float(
        string='Grand Total Gross Weight',
        compute='_compute_grand_total_gross_weight',
        store=True
    )

    description_of_goods = fields.Text(string='Description of Goods')
    manufacture_year_id = fields.Many2one('manufacture.year', string='Year of Manufacture')
    certificate_no = fields.Char(string='Certificate No', readonly=True)

    remarks = fields.Html(string="Remarks")
    packing_details = fields.Html(string="Packing Remarks")
    packing_list_title = fields.Html(string="Packing List Title")

    approve = fields.Boolean(string='Approved', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)

    hr_employee_job_id = fields.Many2one('hr.job',store=True, string= "Job Id")

    cs_in_charge_id = fields.Many2one( comodel_name='res.users', string='CS-In Charge')
    invoice_remarks = fields.Html(string="Invoice Remarks")

    container = fields.Char(string='Container')
    country_of_origin_id = fields.Many2many('res.country', string='Country of Origin')

    is_verified = fields.Boolean(string='Verified', readonly=True)
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verified_on = fields.Datetime(string='Verified On', readonly=True)

    project = fields.Char(string='Project')
    total_debit = fields.Monetary(string='Total Debit', compute='_compute_total_debit',
                                  currency_field='company_currency_id')
    total_credit = fields.Monetary(string='Total Credit', compute='_compute_total_debit',
                                   currency_field='company_currency_id')
    purchase_type_id = fields.Many2one('purchase.type',string='Purchase Type')

    shipper_id = fields.Many2one('res.partner', string='Shipper')
    bill_of_lading_no = fields.Char(string='Bill of Lading No.')
    our_ref_no = fields.Char(string='Our Ref No.')
    coo_chamber_id = fields.Many2one('res.partner', string='COO Chamber')
    purchaser_type = fields.Selection([('procurement', 'Procurement'),('non_procurement', 'Non-Procurement')], string="Purchaser Type", default='procurement')



    def _generate_deferred_entries(self):
        res = super(AccountMove, self)._generate_deferred_entries()

        deferred_moves = self.env['account.move'].search([
            ('deferred_original_move_ids', 'in', self.ids),
            ('state', '=', 'posted')
        ])
        deferred_moves.button_draft()
        return res

    def _compute_total_debit(self):
        for rec in self:
            for record in rec.line_ids:
                rec.total_debit += record.debit
                rec.total_credit += record.credit


    def action_register_payment(self):
        for move in self:
            if move.move_type in ['in_invoice', 'in_refund'] and not move.approve:
                raise UserError(_("You cannot register payment for vendor bills that are not approved."))
        return super(AccountMove, self).action_register_payment()


    @api.onchange('person_incharge_id')
    def onchange_person_incharge_id(self):
        for rec in self:
            rec.hr_employee_job_id = rec.person_incharge_id.job_id.id if rec.person_incharge_id else False

    @api.onchange('forwarder')
    def onchange_forwarder(self):
        for rec in self:
            rec.forwarder_contact = rec.forwarder.phone if rec.forwarder else False

    def action_approve(self):
        for picking in self:
            picking.write({
                'approve': True,
                'approved_by': self.env.user.id,
                'approved_on': datetime.now()
            })

    def action_verify(self):
        for move in self:
            move.write({
                'is_verified': True,
                'verified_by': self.env.user.id,
                'verified_on': fields.Datetime.now()
            })


    def do_generate_certificate_no(self):
        for record in self:
            if record.certificate_no:
                raise UserError(_("Certificate number is already generated."))
            if not record.partner_id:
                raise UserError(_("Please select a partner before generating the certificate number."))

            company = record.partner_id.parent_id if record.partner_id.parent_id else record.partner_id
            company_name = company.name.replace(" ", "").upper()

            seq_number = self.env['ir.sequence'].next_by_code('custom.invoice.certificate')
            record.certificate_no = f"LJS-{company_name}-{seq_number}"

    @api.depends('invoice_line_ids.quantity', 'invoice_line_ids.product_id.weight', 'invoice_line_ids.product_id')
    def _compute_sub_total_net_weight(self):
        for rec in self:
            total_weight = 0.0
            for line in rec.invoice_line_ids:
                product_weight = line.product_id.weight or 0.0
                total_weight += line.quantity * product_weight
            rec.sub_total_net_weight = total_weight

    @api.depends('packaging_gross_weight', 'sub_total_net_weight')
    def _compute_grand_total_gross_weight(self):
        for rec in self:
            rec.net_total = (rec.packaging_gross_weight or 0.0) + (rec.sub_total_net_weight or 0.0)


    def _get_report_lang(self):
        return self.partner_id.lang or self.env.user.lang

    def action_post(self):
        for move in self:
            if move.move_type == 'out_invoice':
                move._validate_invoice_quantities()

            if move.move_type == 'in_invoice':
                move._validate_billed_quantity()
        return super().action_post()

    def _validate_invoice_quantities(self):
        """Raise error if invoiced quantity exceeds sale order quantity."""
        for line in self.invoice_line_ids:
            if not line.sale_line_ids or not line.product_id:
                continue

            for sale_line in line.sale_line_ids:
                order_qty = sale_line.product_uom_qty

                total_invoice_qty = sum(sale_line.invoice_lines.filtered(lambda inv_line: inv_line.move_id.id != self.id and inv_line.move_id.state != 'cancel').mapped('quantity'))

                total_invoice_qty += line.quantity

                if total_invoice_qty > order_qty:
                    raise ValidationError(_("Invoiced quantity exceeds ordered quantity for product '%s'. ") % (line.product_id.display_name))

    def _validate_billed_quantity(self):
        """Raise error if billed quantity exceeds received quantity in PO."""
        for move in self:
            if move.move_type == 'in_invoice':
                for line in move.invoice_line_ids:

                    if line.product_id.name == 'Advance Payment':
                        continue

                    if line.purchase_line_id:
                        po_line = line.purchase_line_id

                        ordered_qty = po_line.product_uom_qty
                        qty = po_line.product_qty

                        billed_qty = line.quantity

                        if billed_qty > qty:
                            raise ValidationError(_("Billed quantity for product '%s' exceeds received quantity. Quantity: %s, Billed: %s.") %
                                                   (line.product_id.display_name, qty, billed_qty))

    def _reverse_moves(self, default_values_list=None, cancel=False):
        default_values_list = default_values_list or []
        for vals in default_values_list:
            if vals.get('auto_post') == 'nothing':
                vals['auto_post'] = 'no'
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

class CNReason(models.Model):
    _name = 'cn.reason'
    _description = 'CN Reason'

    name = fields.Char(string='CN Reason ', required=True)

class ShipmentYear(models.Model):
    _name = 'manufacture.year'
    _description = 'Year of Manufacture'

    name = fields.Char(string='Year', required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Year must be unique.')
    ]

class Port(models.Model):
    _name = 'port.port'
    _description = 'Port'

    name = fields.Char(string='Port Name', required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Port name must be unique.')
    ]



class AccountAsset(models.Model):
    _inherit = 'account.asset'

    asset_code = fields.Char(string='Asset Code')
    location_id = fields.Many2one('asset.location', string="Location")
    models_id = fields.Many2one('asset.model', string="Model")
    user_id = fields.Many2one('hr.employee', string="User")
    remarks = fields.Text(string="Remarks")

    approve = fields.Boolean(string='Approved', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)

    is_verified = fields.Boolean(string='Verified', readonly=True)
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verified_on = fields.Datetime(string='Verified On', readonly=True)

    def action_approve(self):
        for asset in self:
            asset.write({
                'approve': True,
                'approved_by': self.env.user.id,
                'approved_on': datetime.now()
            })

    def action_verify(self):
        for asset in self:
            asset.write({
                'is_verified': True,
                'verified_by': self.env.user.id,
                'verified_on': fields.Datetime.now()
            })

class Location(models.Model):
    _name = 'asset.location'
    _description = 'Location'

    name = fields.Char(string='Location', required=True)


class Model(models.Model):
    _name = 'asset.model'
    _description = 'Model'

    name = fields.Char(string='Model', required=True)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_verified_1 = fields.Boolean(string='1. Verified', readonly=True)
    verified_by_1 = fields.Many2one('res.users', string='1. Verified By', readonly=True)
    verified_on_1 = fields.Datetime(string='1. Verified On', readonly=True)

    is_verified_2 = fields.Boolean(string='2. Verified', readonly=True)
    verified_by_2 = fields.Many2one('res.users', string='2. Verified By', readonly=True)
    verified_on_2 = fields.Datetime(string='2. Verified On', readonly=True)

    is_approved_1 = fields.Boolean(string='1. Approved', readonly=True)
    approved_by_1 = fields.Many2one('res.users', string='1. Approved By', readonly=True)
    approved_on_1 = fields.Datetime(string='1. Approved On', readonly=True)

    is_approved_2 = fields.Boolean(string='2. Approved', readonly=True)
    approved_by_2 = fields.Many2one('res.users', string='2. Approved By', readonly=True)
    approved_on_2 = fields.Datetime(string='2.  On', readonly=True)


    def action_verify_1(self):
        for rec in self:
            rec.write({
                'is_verified_1': True,
                'verified_by_1': self.env.user.id,
                'verified_on_1': fields.Datetime.now()
            })

    def action_verify_2(self):
        for rec in self:
            rec.write({
                'is_verified_2': True,
                'verified_by_2': self.env.user.id,
                'verified_on_2': fields.Datetime.now()
            })

    def action_approve_1(self):
        for rec in self:
            rec.write({
                'is_approved_1': True,
                'approved_by_1': self.env.user.id,
                'approved_on_1': fields.Datetime.now()
            })

    def action_approve_2(self):
        for rec in self:
            rec.write({
                'is_approved_2': True,
                'approved_by_2': self.env.user.id,
                'approved_on_2': fields.Datetime.now()
            })


class AccountMoveLineInherit(models.Model):
    _inherit = "account.move.line"

    sale_order_ids = fields.Many2many('sale.order', string='Sales Orders', readonly=True)
    product_id_domain = fields.Char(string="Product Domain", compute="_compute_product_id_domain", store=False)
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Order')

    revenue_amount = fields.Monetary(string="Revenue",compute="_compute_profit_fields",store=True)
    cost_amount = fields.Monetary(string="Cost",compute="_compute_profit_fields",store=True)
    gross_profit = fields.Monetary(string="Gross Profit",compute="_compute_profit_fields",store=True)

    @api.depends('credit','debit','quantity','product_id','account_id.account_type','move_id.move_type','move_id.line_ids.debit',)
    def _compute_profit_fields(self):
        AnalyticLine = self.env['account.analytic.line']

        for line in self:
            revenue = cost = profit = 0.0

            if (
                    line.move_id.move_type == 'out_invoice'
                    and line.account_id.account_type == 'income'
                    and line.product_id
            ):

                revenue = line.credit - line.debit
                product = line.product_id
                quantity = line.quantity

                external_ids = product.product_tmpl_id.get_external_id()
                is_timesheet_product = (
                        'sale_timesheet.time_product_product_template'
                        in external_ids.values()
                )

                if is_timesheet_product:
                    analytic_lines = AnalyticLine.search([
                        ('timesheet_invoice_id', '=', line.move_id.id)
                    ])
                    cost = abs(sum(analytic_lines.mapped('amount')))

                # Service
                elif product.type == 'service':
                    cost = product.standard_price * line.quantity

                # Goods + Track Inventory = TRUE
                # COST = JOURNAL DEBIT TOTAL
                elif product.type == 'consu' and product.is_storable:
                    expense_account = product.categ_id.property_account_expense_categ_id

                    if expense_account:
                        cost = 0.0
                        cogs_lines = line.move_id.line_ids.filtered(lambda l: (l.account_id.id == expense_account.id) and (l.product_id == product) and (l.quantity == quantity) and (l.debit > 0))
                        if cogs_lines:
                            cost = sum(cogs_lines.mapped('debit')) / len (cogs_lines)

                # Goods + Track Inventory = FALSE
                elif product.type == 'consu' and not product.is_storable:
                    cost = product.standard_price * line.quantity

                profit = revenue - cost

            line.revenue_amount = revenue
            line.cost_amount = cost
            line.gross_profit = profit

    @api.depends('move_id.purchaser_type', 'move_id.move_type', 'company_id')
    def _compute_product_id_domain(self):
        for line in self:
            domain = [
                '|',
                ('company_id', '=', False),
                ('company_id', 'parent_of', line.company_id.id),
            ]
            if line.move_id.move_type in ('in_invoice', 'in_refund'):
                domain.insert(0, ('purchase_ok', '=', True))
                if line.move_id.purchaser_type == 'non_procurement':
                    domain.append(('type', '=', 'service'))

            elif line.move_id.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                domain.insert(0, ('sale_ok', '=', True))

            line.product_id_domain = json.dumps(domain)

    def format_amount(self):
        self.ensure_one()
        amount = self.amount_currency
        if not amount:
            return ""

        currency_id = self.currency_id
        res = "{:,.2f}".format(abs(amount))
        if amount < 0:
            res = "(" + res + ")"
        res = currency_id.symbol + " " + res
        return res

    @api.constrains('account_id', 'analytic_distribution')
    def _check_analytic_distribution(self):
        for line in self:
            move = line.move_id
            if move.move_type in ('in_invoice', 'in_refund'):
                if line.account_id:
                    account_type = line.account_id.account_type
                    if account_type in ['expense', 'expense_direct_cost','expense_depreciation'] and not line.analytic_distribution:
                        raise ValidationError(_("Analytic Distribution is mandatory for accounts of type '%s'. " "Please provide the Analytic Distribution to proceed.") % (account_type.replace('_', ' ').title()))


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def _prepare_default_reversal(self, move):
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)
        res['auto_post'] = 'nothing'
        return res