from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ReportApprovalHandler(models.AbstractModel):
    _name = 'report.lingjack_operation.report_common_handler'
    _description = 'Common Approval Report'

    REPORTS_WITH_APPROVAL = {
        'report.lingjack_operation.report_certificate_beneficiary': 'account.move',
        'report.lingjack_operation.report_confirmation_of_manufacturer': 'account.move',
        'report.lingjack_operation.report_shipment_advice': 'account.move',
        'report.lingjack_operation.report_invoice_certificate_origin': 'account.move',
        'report.lingjack_operation.report_inv_limited_warranty_wrapper': 'account.move',
        'report.lingjack_operation.report_invoice_conformity_certificate': 'account.move',
        'report.lingjack_operation.report_invoice_certificate': 'account.move',
        'report.account.report_invoice': 'account.move',

        'report.lingjack_operation.report_sale_quotation_lingjack': 'sale.order',

    }

    def _check_approval(self, docs):
        for doc in docs:
            if not doc.approve:
                raise UserError(
                    _(f"Please approve this {doc._name.replace('.', ' ').title()} before printing the report."))

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


class ReportBenificiaryCer(models.AbstractModel):
    _name = 'report.lingjack_operation.report_certificate_beneficiary'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationManufact(models.AbstractModel):
    _name = 'report.lingjack_operation.report_confirmation_of_manufacturer'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationShipment(models.AbstractModel):
    _name = 'report.lingjack_operation.report_shipment_advice'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationOrigin(models.AbstractModel):
    _name = 'report.lingjack_operation.report_invoice_certificate_origin'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationLimitedWarranty(models.AbstractModel):
    _name = 'report.lingjack_operation.report_inv_limited_warranty_wrapper'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationConformityCer(models.AbstractModel):
    _name = 'report.lingjack_operation.report_invoice_conformity_certificate'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationQuality(models.AbstractModel):
    _name = 'report.lingjack_operation.report_invoice_certificate'
    _inherit = 'report.lingjack_operation.report_common_handler'


class ReportConfirmationPdfWithoutPayment(models.AbstractModel):
    _name = 'report.account.report_invoice'
    _inherit = 'report.lingjack_operation.report_common_handler'

class SaleQuotation(ReportApprovalHandler):
    _name = 'report.lingjack_operation.report_sale_quotation_lingjack'
    _inherit = 'report.lingjack_operation.report_common_handler'



