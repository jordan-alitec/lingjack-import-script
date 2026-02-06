# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class LingjackListScannerBase(models.AbstractModel):
    """Abstract model to add scanner functionality to any model"""
    _name = 'lingjack.list.scanner.base'
    _description = 'Lingjack List Scanner Base'

    @api.model
    def scan_and_duplicate_record(self, model_name, barcode_value, parent_id,parent_field):
        """
        Search for a record by x_studio_service_id, duplicate it, and link to parent
        
        :param model_name: The model name to search in
        :param barcode_value: The value to search for in x_studio_service_id
        :param parent_id: The parent record ID to link to (x_studio_parent_id)
        :return: dict with status and new record ID
        """
        try:
            # Get the model
            model = self.env[model_name]
            
            parent_record = self.env['project.task'].sudo().search([
                ('id', '=', parent_id)
            ], limit=1)

            if not parent_record:
                return {
                    'status': 'not_found',
                    'message': _('No parent record found with ID: %s') % parent_id
                }
            worksheet = self.env[parent_record.worksheet_template_id.sudo().model_id.model].search([('x_project_task_id', '=', parent_id)], limit=1)
            
            if not worksheet:
                return {
                    'status': 'error',
                    'message': _('Worksheet not found for parent task ID: %s') % parent_id
                }
            
            # Search for record with matching x_studio_service_id
            record = model.search([
                ('x_studio_service_id', '=', barcode_value)
            ], limit=1)
            
            if not record:
                new_record = self.env[model_name].sudo().create({
                    'x_studio_service_id': barcode_value,
                    'x_studio_task': parent_id,
                    parent_field: worksheet.id,
                })
            else:
                new_record = record.copy()
                new_record.write({  
                    parent_field: worksheet.id,
                    'x_studio_task': parent_id,  # Clear the service ID as requested
                })

            # Duplicate the record
            # new_record = record.copy({
            #     'x_studio_parent_id': parent_record.worksheet_template_id.id,
            #     'x_studio_service_id': False,  # Clear the service ID as requested
            # })
            
            return {
                'status': 'success',
                'record_id': new_record.id,
                'message': _('Record duplicated and linked successfully')
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
