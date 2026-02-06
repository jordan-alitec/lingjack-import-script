# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools import SQL
from odoo.exceptions import UserError

class AccountInvoiceReportCustom(models.Model):
    _inherit = "account.invoice.report"

    margin_percent_cost = fields.Float(string='Margin % (Cost)',readonly=True)
    margin_percent_revenue = fields.Float(string='Margin % (Revenue)',readonly=True)



    @api.model
    def _select(self) -> SQL:
        base_select = super()._select()

        extra_select = SQL(''', ((CASE
                    WHEN move.move_type NOT IN ('out_invoice', 'out_receipt', 'out_refund') THEN 0.0
                    WHEN move.move_type = 'out_refund' THEN account_currency_table.rate * (-line.balance + (line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0)) * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float)
                    ELSE account_currency_table.rate * (-line.balance - (line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0)) * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float)
                END ) / NULLIF(ABS(-line.balance * account_currency_table.rate),0)) * 100  AS margin_percent_revenue ,
                
               ((CASE
                    WHEN move.move_type NOT IN ('out_invoice', 'out_receipt', 'out_refund') THEN 0.0
                    WHEN move.move_type = 'out_refund' THEN account_currency_table.rate * (-line.balance + (line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0)) * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float)
                    ELSE account_currency_table.rate * (-line.balance - (line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0)) * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float)
                END ) / NULLIF(
                        ABS(
                            account_currency_table.rate * line.quantity 
                            / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0) 
                            * (CASE WHEN move.move_type IN ('out_invoice','in_refund','out_receipt') THEN -1 ELSE 1 END)
                            * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float
                        ), 0)
                ) * 100 AS margin_percent_cost
                
            
        ''')

        return SQL("%s %s", base_select, extra_select)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(AccountInvoiceReportCustom, self).read_group( domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy )

        for group in res:
            if 'price_subtotal' in group and 'price_margin' in group:
                price_subtotal = group['price_subtotal'] or 0.0
                price_margin = group['price_margin'] or 0.0
                inventory_value = group.get('inventory_value', 0.0)

                group['margin_percent_revenue'] = (price_subtotal and (price_margin / abs(price_subtotal)) * 100) or 0.0
                group['margin_percent_cost'] = (inventory_value and (price_margin / abs(inventory_value)) * 100) or 0.0
        return res

class ReportExportInvoice(models.AbstractModel):
    _name = 'report.lingjack_print.export_invoice'
    _description = 'Export Invoice Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)

        for doc in docs:
            if doc.amount_tax_signed != 0:
                raise UserError("You are not allowed to print this invoice because Tax Signed is not 0.")

        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
        }


class AccountMove(models.Model):
    _inherit = "account.move"


    tax_totals_without_dp = fields.Binary(
        string="Invoice Without Dp Totals",
        compute='_compute_without_dp_tax_totals',
        inverse='_inverse_tax_totals_without_dp',
        help='Edit Tax amounts if you encounter rounding issues.',
        exportable=False,
    )


    def _get_rounded_base_without_dp_and_tax_lines(self, round_from_tax_lines=True):
        """ Small helper to extract the base and tax lines for the taxes computation from the current move.
        The move could be stored or not and could have some features generating extra journal items acting as
        base lines for the taxes computation (e.g. epd, rounding lines).

        :param round_from_tax_lines:    Indicate if the manual tax amounts of tax journal items should be kept or not.
                                        It only works when the move is stored.
        :return:                        A tuple <base_lines, tax_lines> for the taxes computation.
        """
        self.ensure_one()
        AccountTax = self.env['account.tax']
        is_invoice = self.is_invoice(include_receipts=True)

        if self.id or not is_invoice:
            base_amls = self.line_ids.filtered(lambda line: line.display_type == 'product' and not line.is_downpayment)
        else:
            base_amls = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product' and not line.is_downpayment)
        base_lines = [self._prepare_product_base_line_for_taxes_computation(line) for line in base_amls]

        tax_lines = []
        if self.id:
            # The move is stored so we can add the early payment discount lines directly to reduce the
            # tax amount without touching the untaxed amount.
            epd_amls = self.line_ids.filtered(lambda line: line.display_type == 'epd' and not line.is_downpayment)
            base_lines += [self._prepare_epd_base_line_for_taxes_computation(line) for line in epd_amls]
            cash_rounding_amls = self.line_ids \
                .filtered(
                lambda line: line.display_type == 'rounding' and not line.tax_repartition_line_id and not line.is_downpayment)
            base_lines += [self._prepare_cash_rounding_base_line_for_taxes_computation(line) for line in cash_rounding_amls]
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            # tax_amls = self.line_ids.filtered('tax_repartition_line_id' 'is_downpayment')
            tax_amls = self.line_ids.filtered(lambda line: line.tax_repartition_line_id and not line.is_downpayment)
            tax_lines = [self._prepare_tax_line_for_taxes_computation(tax_line) for tax_line in tax_amls]
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id,
                                                     tax_lines=tax_lines if round_from_tax_lines else [])
        else:
            # The move is not stored yet so the only thing we have is the invoice lines.
            base_lines += self._prepare_epd_base_lines_for_taxes_computation_from_base_lines(base_amls)
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return base_lines, tax_lines


    @api.depends_context('lang')
    @api.depends(
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_line_ids.price_total',
        'invoice_line_ids.price_subtotal',
        'invoice_payment_term_id',
        'partner_id',
        'currency_id',
    )
    def _compute_without_dp_tax_totals(self):
        """ Computed field used for custom widget's rendering.
            Only set on invoices.
        """
        for move in self:
            if move.is_invoice(include_receipts=True):
                base_lines, _tax_lines = move._get_rounded_base_without_dp_and_tax_lines()
                move.tax_totals_without_dp = self.env['account.tax'].with_context(without_dp_lines=True)._get_tax_totals_summary(
                    base_lines=base_lines,
                    currency=move.currency_id,
                    company=move.company_id,
                    cash_rounding=move.invoice_cash_rounding_id,
                )
                move.tax_totals_without_dp['display_in_company_currency'] = (
                        move.company_id.display_invoice_tax_company_currency
                        and move.company_currency_id != move.currency_id
                        and move.tax_totals_without_dp['has_tax_groups']
                        and move.is_sale_document(include_receipts=True)
                )
            else:
                # Non-invoice moves don't support that field (because of multicurrency: all lines of the invoice share the same currency)
                move.tax_totals_without_dp = None


    def _inverse_tax_totals_without_dp(self):
        with self._disable_recursion({'records': self}, 'skip_invoice_sync') as disabled:
            if disabled:
                return
        with self._sync_dynamic_line(
            existing_key_fname='term_key',
            needed_vals_fname='needed_terms',
            needed_dirty_fname='needed_terms_dirty',
            line_type='payment_term',
            container={'records': self},
        ):
            for move in self:
                if not move.is_invoice(include_receipts=True):
                    continue
                invoice_totals = move.tax_totals

                for subtotal in invoice_totals['subtotals']:
                    for tax_group in subtotal['tax_groups']:
                        tax_lines = move.line_ids.filtered(lambda line: line.tax_group_id.id == tax_group['id'])

                        if tax_lines:
                            first_tax_line = tax_lines[0]
                            tax_group_old_amount = sum(tax_lines.mapped('amount_currency'))
                            sign = -1 if move.is_inbound() else 1
                            delta_amount = tax_group_old_amount * sign - tax_group['tax_amount_currency']

                            if not move.currency_id.is_zero(delta_amount):
                                first_tax_line.amount_currency -= delta_amount * sign
            self._compute_amount()
