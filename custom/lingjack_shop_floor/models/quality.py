# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
_logger = logging.getLogger(__name__)

class QualityPoint(models.Model):
    _inherit = 'quality.point'

    show_in_quality_module = fields.Boolean(
        string="Show in Quality Module",
        default=False,
        help="If checked, this quality control point will be visible in the quality module"
    )
    
    # Field to enable automatic data injection into second sheet
    auto_inject_data = fields.Boolean(
        string="Auto Inject Data to Second Sheet",
        default=True,
        help="If checked, quality check data will be automatically injected into a second sheet"
    )

    @api.onchange('operation_id')
    def _onchange_operation_id(self):
        """Set show_in_quality_module to True when operation_id is set"""
        if self.operation_id:
            self.show_in_quality_module = True
        else:
            self.show_in_quality_module = False

class QualityCheck(models.Model):
    _inherit = 'quality.check'
    qc_type = fields.Selection([('incoming','Incoming'),('outgoing','Outgoing')], string='QC Type', default='outgoing')

    show_in_quality_module = fields.Boolean(
        string="Show in Quality Module",
        related='point_id.show_in_quality_module',
        readonly=True,
        store=True,
        help="If checked, this quality check will be visible in the quality module"
    )
    
    # New field to store whether data was injected
    data_injected = fields.Boolean(
        string="Data Injected",
        help="Indicates if quality check data was automatically injected into spreadsheet"
    )

    def _create_spreadsheet_from_template(self):
        """Override to inject quality check data into the second sheet"""
        self.ensure_one()
        
        # Call the parent method to create the spreadsheet
        spreadsheet = super()._create_spreadsheet_from_template()

        # Inject quality check data if enabled
        if self.point_id.auto_inject_data:
            self._inject_qc_data_into_second_sheet(spreadsheet)
            self.data_injected = True
        
        return spreadsheet

    def inject_qc(self):
        self._inject_qc_data_into_second_sheet(self.spreadsheet_id)

    def _inject_qc_data_into_second_sheet(self, spreadsheet):
        """Inject quality check data into the second sheet of the spreadsheet"""
        try:
            # Parse the existing spreadsheet data
            if spreadsheet.spreadsheet_data:
                data = json.loads(base64.b64decode(spreadsheet.spreadsheet_snapshot.decode('utf-8')).decode('utf-8'))
            else:
                data = {"version": 20, "sheets": [{"id": "Sheet1", "name": "Sheet1", "cells": {}}]}
            
            # Ensure we have at least one sheet
            if not data.get("sheets"):
                data["sheets"] = [{"id": "Sheet1", "name": "Sheet1", "cells": {}}]

            

            # Find the Data sheet (could be any sheet, we'll look for it)
            data_sheet = None
            for sheet in data["sheets"]:
                sheet_name = sheet.get("name", "").lower()
                if sheet_name == "data":
                    data_sheet = sheet

                    break
            
            # If no Data sheet found, create it
            if not data_sheet:
                data_sheet = {
                    "id": "Data",
                    "name": "Data",
                    "cells": {}
                }
                data["sheets"].append(data_sheet)

            
            if "cells" not in data_sheet:
                data_sheet["cells"] = {}

            
            # Log all cells in Data sheet

            
            # Read field paths from Column A of the Data sheet
            field_mappings = []
            row = 1
            while True:
                cell_key = f"A{row}"

                if cell_key in data_sheet["cells"]:
                    cell_content = data_sheet["cells"][cell_key]

                    field_path = cell_content.get("content", "").strip()

                    if field_path:  # Only add non-empty field paths
                        field_mappings.append(field_path)

                    row += 1
                else:

                    break
            

            
            # If no field mappings found in Column A, use default mappings
            if not field_mappings:

                field_mappings = [
                    "picking_id.name",
                    "production_id.product_id.name", 
                    "partner_id.name",
                    "name",
                    "test_type",
                    "state"
                ]
                # Write default mappings to Column A
                for i, field_path in enumerate(field_mappings, 1):
                    data_sheet["cells"][f"A{i}"] = {
                        "content": field_path,
                        "style": 1  # Basic style
                    }

            
            # Populate Column B with field values
            for i, field_path in enumerate(field_mappings, 1):
                # Get field value and write in Column B
                field_value = self._get_field_value_by_path(field_path)

                data_sheet["cells"][f"B{i}"] = {
                    "content": str(field_value) if field_value is not None else "",
                    "style": 1  # Basic style
                }

            
            # Update the spreadsheet data
            spreadsheet.spreadsheet_data = json.dumps(data)
            

        except Exception as e:
            # Log the error but don't fail the process
            import traceback

    def _get_field_value_by_path(self, field_path):
        """Get field value by dot notation path (e.g., 'picking_id.name')"""
        try:
            current_obj = self
            for field_name in field_path.split('.'):
                if hasattr(current_obj, field_name):
                    current_obj = getattr(current_obj, field_name)
                else:
                    return None
                
                # Handle Many2one fields
                if hasattr(current_obj, 'name') and not field_name.endswith('_id'):
                    # If it's a recordset with a name field, get the name
                    if hasattr(current_obj, '__iter__') and len(current_obj) == 1:
                        current_obj = current_obj.name
                    elif hasattr(current_obj, '__iter__') and len(current_obj) > 1:
                        # Multiple records, return comma-separated names
                        current_obj = ', '.join(current_obj.mapped('name'))
            
            return current_obj
        except Exception as e:
            return None

    def force_inject_qc_data(self):
        """Force inject the QC data into the Data sheet - useful for debugging"""
        self.ensure_one()
        
        if not self.point_id.auto_inject_data:
            raise UserError(_("Auto inject data is not enabled for this quality point"))
        
        if not self.spreadsheet_id:
            # Create spreadsheet if it doesn't exist
            self.spreadsheet_id = self._create_spreadsheet_from_template()
        else:
            # Inject into existing spreadsheet
            self._inject_qc_data_into_second_sheet(self.spreadsheet_id)
            self.data_injected = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Injection Complete'),
                'message': _('QC data injected into Data sheet based on field mappings'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_spreadsheet2(self):
        self.ensure_one()
        if not self.spreadsheet_id:
            raise UserError(_("No spreadsheet found for this quality check. Please create a spreadsheet first."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('QC Spreadsheet - Data Sheet'),
            'res_model': 'quality.check.spreadsheet',
            'res_id': self.spreadsheet_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
    #
    # def action_print_sheet2(self):
    #     """Open sheet 2 of the spreadsheet"""
    #     self.ensure_one()
    #
    #     if not self.spreadsheet_id:
    #         raise UserError(_("No spreadsheet found for this quality check. Please create a spreadsheet first."))
    #
    #     # Ensure QC data is injected into sheet 2
    #     if not self.data_injected and self.point_id.auto_inject_data:
    #         self._inject_qc_data_into_second_sheet(self.spreadsheet_id)
    #         self.data_injected = True
    #
    #     # Open the spreadsheet with sheet 2 active
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _('Sheet 2 - QC Data'),
    #         'res_model': 'documents.document',
    #         'res_id': self.spreadsheet_id.id,
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_spreadsheet_data': self.spreadsheet_id.spreadsheet_data,
    #             'default_active_sheet_id': 'Sheet2',
    #         }
    #     }

class QualityTemplate(models.Model):
    _inherit = 'quality.point'
    is_locked = fields.Boolean(string='Is Locked')