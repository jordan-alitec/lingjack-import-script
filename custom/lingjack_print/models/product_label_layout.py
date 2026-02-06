from odoo import api, fields, models, _
import time
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)
import qrcode
import base64
from io import BytesIO

class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(selection_add=[('dymo_production_label', 'Dymo Production Incoming Label')], ondelete={'dymo_production_label': 'set default'})

    def _prepare_report_data(self):
        if self.print_format != 'dymo_production_label':
            return super()._prepare_report_data()

        active_id = self.env.context.get('active_id')
        if not active_id:
            raise UserError(_('No active production order found in context.'))

        # Prepare custom data for the report
        data = {
            'mo_id': active_id,
            'print_format': self.print_format,
            'custom_quantity': self.custom_quantity or 1,
        }
        xml_id = 'lingjack_print.action_report_production_incoming_label'
        return xml_id, data

class ReportProductionIncomingLabel(models.AbstractModel):
    _name = 'report.lingjack_print.report_production_incoming_label_template'
    _description = 'Production Incoming Label'


    @api.model
    def _get_report_values(self, docids, data=None):

        mo_id = docids or data['context']['active_id']
        if not mo_id:
            raise UserError(_('No production data provided for the report.'))

        mo = self.env['mrp.production'].browse(mo_id)
        if not mo:
            raise UserError(_('Invalid production order ID.'))

        custom_quantity = data.get('custom_quantity', 3)  # Get custom_quantity from data, default to 1

        # Generate QR codes using the helper function
        qr_pwo_base64 = f'mo:{mo.name}'
        qr_product_base64 = mo.product_id.default_code

        # Build doc dict based on template expectations
        so = mo.procurement_group_id.sale_id
        doc = {
            'product_name': mo.product_id.name or '',
            'product_default_code': mo.product_id.default_code or '',
            'sale_order_number': ",".join(mo.sale_order_ids.mapped('name')) or '',
            'pwo_number': mo.name or '',
            'customer_name':",".join(mo.sale_order_ids.mapped('partner_id.name')) or '',
            'project_name': mo.project_id.name or '',
            'pwo_no': mo.name or '',
            # 'planned_qty': sum(mo.backorder_ids.mapped('product_qty')) if mo.backorder_ids else mo.product_qty,
            'planned_qty': sum(mo.procurement_group_id.mrp_production_ids.mapped('product_qty')) if mo.procurement_group_id.mrp_production_ids else mo.product_qty,
            'qc_checked': mo.product_qty or '',
            'remark': mo.remark or '',
            'pwo_number_qr': qr_pwo_base64,
            'product_code_qr': qr_product_base64, # Add QR code for product code
            'lines': []
        }

        # Use raw materials for lines (incoming); adjust to move_finished_ids if needed
        for idx, move in enumerate(mo.move_raw_ids, 1):
            doc['lines'].append({
                'index': idx,
                'com_no': move.reference or move.product_id.default_code or '',
                'description': move.product_id.name or '',
                'planned_qty': move.product_qty,
                'qc_checked_qty': move.product_uom_qty
            })

        # Repeat the doc based on quantity
        docs = [doc] * max(1, int(custom_quantity))  # Ensure at least 1 copy

        return {
            'doc_ids': [mo.id] * max(1, int(custom_quantity)),  # Repeat IDs to match docs
            'doc_model': 'mrp.production',
            'docs': docs,
            'time': time,
        }