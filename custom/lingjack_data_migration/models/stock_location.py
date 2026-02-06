# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    @api.model
    def loan_note_api_create_loan(self, vals):
        """
        API endpoint to create a Loan note.
        """
        if not vals.get('name'):
            raise ValidationError("Location name is required")

        location_name = vals.get('name').strip()
        existing_location = self.search([('name', '=', location_name)], limit=1)
        if existing_location:
            return {
                'status': 'exists',
                'location_id': existing_location.id,
                'name': existing_location.name,
            }

        parent_location = self.env['stock.location'].search([('name','=','Loan'),('company_id','=',self.env.company.id)])
        if parent_location:
            try:
                vals['location_id'] = parent_location.id
                new_location = self.create(vals)

                return {
                    'status': 'created',
                    'location_id': new_location.id,
                    'name': new_location.name,
                }

            except Exception as e:
                raise UserError(f"Error creating location: {str(e)}")
