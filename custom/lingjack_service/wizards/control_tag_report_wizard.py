# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import logging

_logger = logging.getLogger(__name__)


class ControlTagReportWizard(models.TransientModel):
    _name = 'control.tag.report.wizard'
    _description = 'Control Tag Report Wizard'

    date_from = fields.Date(string='Invoice Date From', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Invoice Date To', required=True, default=fields.Date.today)
    note = fields.Text(string='Note', help='Optional note shown on the report (e.g. missing items, police report ref).')

    excel_file = fields.Binary(string='Excel File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            return {
                'warning': {
                    'title': _('Invalid Date Range'),
                    'message': _('Date From cannot be later than Date To.'),
                }
            }

    def action_generate_excel(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_('Date From cannot be later than Date To.'))

        excel_data = self._generate_excel_content()
        file_name = f'Control_Tag_Report_{self.date_from}_{self.date_to}.xlsx'
        self.write({
            'excel_file': base64.b64encode(excel_data),
            'file_name': file_name,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Control Tag Report Generated'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _generate_excel_content(self):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('XlsxWriter is required. Please install it: pip install xlsxwriter'))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'left',
            'valign': 'vcenter',
        })
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#F2DCDB',
        })
        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
        })
        cell_format_center = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })

        worksheet = workbook.add_worksheet('Control Tag Report')

        # Column headers (match sample: Number, Company Name, Date, Customer Reference, Project Name, Item Code, Item Description, Control Tag, SO Qty, Key By, Sales Person, PO #)
        headers = [
            'Number',
            'Company Name',
            'Date',
            'Customer Reference',
            'Project Name',
            'Item Code',
            'Item Description',
            'Control Tag',
            'SO Qty',
            'Key By',
            'Sales Person',
            'PO #',
        ]

        rows_data = self._get_control_tag_data()

        # Column widths
        col_widths = [8, 25, 12, 18, 18, 14, 30, 18, 8, 12, 18, 14]
        for col_idx, w in enumerate(col_widths):
            worksheet.set_column(col_idx, col_idx, w)

        # Row 1: Title
        worksheet.write('A1', 'Control Tag Report', title_format)

        # Row 2: Note (optional)
        if self.note:
            worksheet.write('J2', 'Note :', workbook.add_format({'bold': True}))
            worksheet.write('K2', self.note, cell_format)

        # Row 4: Headers
        for col_idx, header in enumerate(headers):
            worksheet.write(3, col_idx, header, header_format)

        # Data rows (from row 5, 0-based row 4)
        for row_idx, row in enumerate(rows_data, start=4):
            worksheet.write(row_idx, 0, row['number'], cell_format_center)
            worksheet.write(row_idx, 1, row['company_name'] or '', cell_format)
            worksheet.write(row_idx, 2, row['date'] or '', cell_format)
            worksheet.write(row_idx, 3, row['customer_reference'] or '', cell_format)
            worksheet.write(row_idx, 4, row['project'] or '', cell_format)
            worksheet.write(row_idx, 5, row['item_code'] or '', cell_format)
            worksheet.write(row_idx, 6, row['item_description'] or '', cell_format)
            worksheet.write(row_idx, 7, row['control_tag'] or '', cell_format)
            worksheet.write(row_idx, 8, row['quantity'], cell_format_center)
            worksheet.write(row_idx, 9, row['key_by'] or '', cell_format)
            worksheet.write(row_idx, 10, row['salesperson'] or '', cell_format)
            worksheet.write(row_idx, 11, row['purchase_order'] or '', cell_format)

        workbook.close()
        output.seek(0)
        return output.getvalue()

    def _get_control_tag_data(self):
        """Get control.tag records in invoice date range."""
        tags = self.env['control.tag'].search([
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ], order='invoice_date, name')

        rows = []
        for i, tag in enumerate(tags, 1):
            item_description = ''
            if tag.move_line_id and tag.move_line_id.product_id:
                item_description = tag.move_line_id.product_id.display_name or tag.move_line_id.product_id.name
            rows.append({
                'number': i,
                'company_name': tag.customer_name or '',
                'date': tag.invoice_date.strftime('%d/%m/%Y') if tag.invoice_date else '',
                'customer_reference': tag.customer_reference or '',
                'project': tag.project or '',
                'item_code': tag.item_code or '',
                'item_description': item_description,
                'control_tag': tag.name or '',
                'quantity': tag.quantity or 0,
                'key_by': tag.key_by or '',
                'salesperson': tag.salesperson or '',
                'purchase_order': tag.purchase_order or '',
            })
        return rows

    def action_download_excel(self):
        self.ensure_one()
        if not self.excel_file:
            raise UserError(_('Please generate the Excel file first.'))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&filename_field=file_name&download=true',
            'target': 'self',
        }
