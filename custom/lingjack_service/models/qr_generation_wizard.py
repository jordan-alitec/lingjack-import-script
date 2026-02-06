# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import qrcode
import io
import base64
import json


class QrGenerationWizard(models.TransientModel):
    _name = 'qr.generation.wizard'
    _description = 'QR Code Generation Wizard'

    generation_type = fields.Selection([
        ('quantity', 'By Quantity'),
        ('range', 'By Range (Start - End)'),
    ], string='Generation Type', default='quantity', required=True)
    
    start_sequence_input = fields.Integer(
        string='Start Sequence',
        required=True,
        help='Starting sequence number for QR codes'
    )
    
    end_sequence_input = fields.Integer(
        string='End Sequence',
        help='Ending sequence number for QR codes (used when generation type is "By Range")'
    )
    
    quantity = fields.Integer(
        string='Quantity',
        default=1,
        help='Number of QR codes to generate (used when generation type is "By Quantity")'
    )
    
    # Fields to store generated data for report
    qr_codes = fields.Text(string='QR Codes Data', help='JSON data of generated QR codes')
    total_count = fields.Integer(string='Total Count', help='Total number of QR codes generated')
    start_sequence = fields.Integer(string='Start Sequence', help='Starting sequence number')
    end_sequence = fields.Integer(string='End Sequence', help='Ending sequence number')
    
    @api.model
    def default_get(self, fields_list):
        """Set default start sequence from company settings"""
        res = super().default_get(fields_list)
        company = self.env.company
        if 'start_sequence_input' in fields_list:
            res['start_sequence_input'] = company.last_used_qr_sequence 
            company.sudo().last_used_qr_sequence = company.last_used_qr_sequence + 1
        return res
    
    @api.onchange('generation_type')
    def _onchange_generation_type(self):
        """Clear fields based on generation type"""
        if self.generation_type == 'range':
            self.quantity = 1
        else:
            self.end_sequence_input = False
    
    @api.constrains('start_sequence_input', 'end_sequence_input', 'quantity')
    def _check_sequences(self):
        """Validate sequence inputs"""
        if self.generation_type == 'range':
            if self.end_sequence_input and self.start_sequence_input >= self.end_sequence_input:
                raise ValidationError(_('Start sequence must be less than end sequence.'))
        elif self.generation_type == 'quantity':
            if self.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than 0.'))
    
    def action_generate_qr_codes(self):
        """Generate QR codes and return PDF report"""
        self.ensure_one()
        
        # Determine the sequence range
        if self.generation_type == 'range':
            if not self.end_sequence_input:
                raise ValidationError(_('End sequence is required for range generation.'))
            start_seq = self.start_sequence_input
            end_seq = self.end_sequence_input
        else:
            start_seq = self.start_sequence_input
            end_seq = self.start_sequence_input + self.quantity - 1
        
        # Generate QR codes data
        qr_data = []
        for seq in range(start_seq, end_seq + 1):
            service_id = f"S{seq:07d}"
            qr_data.append({
                'service_id': service_id,
                'sequence': seq
            })
        
        # Update company's last used sequence
        company = self.env.company
        if end_seq > company.last_used_qr_sequence:
            company.sudo().write({
                'last_used_qr_sequence': end_seq
            })

        
        # Generate QR codes
        qr_codes = []
        for data in qr_data:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data['service_id'])
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            qr_codes.append({
                'service_id': data['service_id'],
                'qr_image': base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            })
        
        # Store data in the wizard record for the report
        self.write({
            'qr_codes': json.dumps(qr_codes),
            'total_count': len(qr_codes),
            'start_sequence': start_seq,
            'end_sequence': end_seq
        })
        
        # Return PDF report
        return {
            'type': 'ir.actions.report',
            'report_name': 'lingjack_service.service_qr_report_template',
            'report_type': 'qweb-pdf',
            'context': dict(self.env.context, active_ids=self.ids, active_id=self.id),
        }
