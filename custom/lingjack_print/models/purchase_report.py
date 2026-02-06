from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ReportPurchaseOrigin(models.AbstractModel):
    _name = 'report.lingjack_print.report_purchase_certificate_origin'

    @api.model
    def _get_report_values(self, docids, data=None):
        """ Endpoint for PDF display. """
        docs = self.env['purchase.order'].browse(docids)
        for rec in docs:
            if rec.state not in ['done','purchase']:
                raise UserError(_("You can not print PO if it's not Done or Purchase."))
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.order',
            'docs': docs,
            'data': data,
        }
