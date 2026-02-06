from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ReportApprovalHandler(models.AbstractModel):
    _name = 'report.lingjack_print.report_common_handler'
    _description = 'Common Approval Report'

    REPORTS_WITH_APPROVAL = {
        'report.lingjack_print.report_confirmation_of_manufacturer': 'account.move',
        'report.account.report_invoice': 'account.move',
        'report.lingjack_print.journal_voucher_invoice': 'account.move',
        'report.lingjack_print.report_tax_invoice': 'account.move',
        'report.lingjack_print.report_tax_invoice_with_delivery': 'account.move',
        'report.lingjack_print.commercial_invoice': 'account.move',
        'report.lingjack_print.export_tax_invoice': 'account.move',

        'report.lingjack_print.report_sale_quotation_lingjack': 'sale.order',

    }

    def _check_approval(self, docs):
        report_name = self._name

        for doc in docs:
            if not doc.approve:
                raise UserError(
                    _(f"Please approve this {doc._name.replace('.', ' ').title()} before printing the report."))

            if report_name == 'report.lingjack_print.commercial_invoice' and doc.amount_tax_signed != 0:
                raise UserError(
                    _(f"You are not allowed to print this commercial invoice because Tax Signed is not 0.")
                )

    def _get_report_values(self, docids, data=None):
        report_name = self._name

        model_name = self.REPORTS_WITH_APPROVAL.get(report_name)
        if not model_name:
            raise UserError(_("Report not configured for approval check"))

        docs = self.env[model_name].browse(docids)

        self._check_approval(docs)

        return {
            'doc_ids': docids,
            'doc_model': model_name,
            'docs': docs,
            'report_name': report_name,
        }


class ReportConfirmationManufact(models.AbstractModel):
    _name = 'report.lingjack_print.report_confirmation_of_manufacturer'
    _inherit = 'report.lingjack_print.report_common_handler'


class ReportJournalVoucher(models.AbstractModel):
    _name = 'report.lingjack_print.journal_voucher_invoice'
    _inherit = 'report.lingjack_print.report_common_handler'

class ReportCommercialInvoice(models.AbstractModel):
    _name = 'report.lingjack_print.commercial_invoice'
    _inherit = 'report.lingjack_print.report_common_handler'

class ReportExportTaxInvoice(models.AbstractModel):
    _name = 'report.lingjack_print.export_tax_invoice'
    _inherit = 'report.lingjack_print.report_common_handler'


class ReportTaxInvoice(models.AbstractModel):
    _name = 'report.lingjack_print.report_tax_invoice'
    _inherit = 'report.lingjack_print.report_common_handler'


class ReportInvoiceAndDeliveryOrder(models.AbstractModel):
    _name = 'report.lingjack_print.report_tax_invoice_with_delivery'
    _inherit = 'report.lingjack_print.report_common_handler'


class ReportConfirmationPdfWithoutPayment(models.AbstractModel):
    _name = 'report.account.report_invoice'
    _inherit = 'report.lingjack_print.report_common_handler'


class SaleQuotation(ReportApprovalHandler):
    _name = 'report.lingjack_print.report_sale_quotation_lingjack'
    _inherit = 'report.lingjack_print.report_common_handler'
