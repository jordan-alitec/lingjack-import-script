from odoo import api, fields, models, _
import base64
import json
import logging

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    qc_template_id = fields.Many2one('quality.spreadsheet.template', string='QC Template', ondelete='set null', help='Quality spreadsheet template to instantiate when an MO is created for this BoM')


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    qc_spreadsheet_id = fields.Many2one('quality.check.spreadsheet', string='QC Spreadsheet', ondelete='set null', index=True)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # procurement_group_id = fields.Many2one('procurement.group', compute='_compute_procurement_group', store=True, readonly=False)
    qc_spreadsheet_id = fields.Many2one('quality.check.spreadsheet', related='procurement_group_id.qc_spreadsheet_id', store=True, readonly=True)

    # Default will deny user in setting component same as the final product
    def _onchange_product_id(self):
        return

    def action_confirm(self):
        res = super().action_confirm()
        to_process = self.filtered(lambda p: p.bom_id and p.bom_id.qc_template_id)
        if not to_process:
            return res
        Spreadsheet = self.env['quality.check.spreadsheet']
        for mo in to_process:
            # Ensure procurement group is present
            if not mo.procurement_group_id:
                group = mo.move_raw_ids[:1].group_id or mo.move_finished_ids[:1].group_id
                if not group:
                    group = self.env['procurement.group'].create({'name': _('MO %s') % mo.name})
                mo.procurement_group_id = group.id
            template = mo.bom_id.qc_template_id
            sheet = mo.procurement_group_id.qc_spreadsheet_id
            if not sheet:
                vals = {
                    'name': _('%s / QC Sheet') % (mo.procurement_group_id.name or mo.procurement_group_id.id),
                    'check_cell': template.check_cell,
                    'spreadsheet_data': template.spreadsheet_data,
                }
                sheet = Spreadsheet.create(vals)
                sheet.spreadsheet_snapshot = template.spreadsheet_snapshot
                template._copy_revisions_to(sheet)
                mo.procurement_group_id.qc_spreadsheet_id = sheet.id
            # Inject MO data into the QC spreadsheet's Data sheet
            try:
                mo._inject_mo_data_into_spreadsheet(sheet)
            except:
                pass
        return res

    def action_open_qc_spreadsheet(self):
        self.ensure_one()
        sheet = self.qc_spreadsheet_id
        if not sheet:
            return False
        return sheet.action_open_spreadsheet()

    def _inject_mo_data_into_spreadsheet(self, spreadsheet):
        self.ensure_one()
        # Load spreadsheet JSON from snapshot if available, otherwise from data
        data = None
        if getattr(spreadsheet, 'spreadsheet_snapshot', False):
            try:
                data = json.loads(base64.b64decode(spreadsheet.spreadsheet_snapshot.decode('utf-8')).decode('utf-8'))
            except Exception:
                data = None
        if data is None:
            try:
                data = json.loads(spreadsheet.spreadsheet_data or '{}') if spreadsheet.spreadsheet_data else {}
            except Exception:
                data = {}
        if not data:
            data = {"version": 20, "sheets": [{"id": "Sheet1", "name": "Sheet1", "cells": {}}]}
        # Ensure at least one sheet list exists
        data.setdefault("sheets", [])
        if not data["sheets"]:
            data["sheets"].append({"id": "Sheet1", "name": "Sheet1", "cells": {}})
        # Find or create Data sheet
        data_sheet = None
        for sheet in data["sheets"]:
            if sheet.get("name", "").lower() == "data":
                data_sheet = sheet
                break
        if not data_sheet:
            data_sheet = {"id": "Data", "name": "Data", "cells": {}}
            data["sheets"].append(data_sheet)
        data_sheet.setdefault("cells", {})
        # Read field mappings from Column A
        field_mappings = []
        row = 1
        while True:
            cell_key = f"A{row}"
            cell = data_sheet["cells"].get(cell_key)
            if cell and cell.get("content"):
                field_path = str(cell.get("content")).strip()
                if field_path:
                    field_mappings.append(field_path)
                row += 1
            else:
                break
        # Provide defaults if no mappings found
        if not field_mappings:
            field_mappings = [
                "name",
                "product_id.display_name",
                "product_qty",
                "bom_id.display_name",
                "state",
            ]
            for i, field_path in enumerate(field_mappings, 1):
                data_sheet["cells"][f"A{i}"] = {"content": field_path, "style": 1}
        # Populate Column B with evaluated values from MO
        for i, field_path in enumerate(field_mappings, 1):
            value = self._get_field_value_by_path_mo(field_path)
            data_sheet["cells"][f"B{i}"] = {"content": '' if value is None else str(value), "style": 1}
        # Save back to spreadsheet
        spreadsheet.spreadsheet_data = json.dumps(data)

    def _get_field_value_by_path_mo(self, field_path):
        try:
            current_obj = self
            for token in field_path.split('.'):
                if not hasattr(current_obj, token):
                    return None
                current_obj = getattr(current_obj, token)
                # Handle recordsets and Many2one display
                if hasattr(current_obj, 'name') and not token.endswith('_ids'):
                    # Single record: return record for further traversal; stringify at end
                    pass
            # Stringify values
            if isinstance(current_obj, models.Model):
                # Recordset: single -> name_get; multi -> join names
                if len(current_obj) == 1:
                    return current_obj.display_name if hasattr(current_obj, 'display_name') else current_obj.name
                return ', '.join(current_obj.mapped(lambda r: getattr(r, 'display_name', r.name)))
            return current_obj
        except Exception as e:
            return None
