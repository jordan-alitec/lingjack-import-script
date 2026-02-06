# -*- coding: utf-8 -*-
#import of odoo
from odoo import api,fields, models

class MrpOperationTemplate(models.Model):
    _name = 'mrp.operation.template'
    _description = 'MRP Operation Template'

    name = fields.Char(string='Name')
    work_center_id = fields.Many2one("mrp.workcenter",string="Work Center")
    reference = fields.Char(string="Reference")
    work_sheet_type = fields.Selection([
        ('pdf', 'PDF'), ('google_slide', 'Google Slide'), ('text', 'Text')],
        string="Worksheet", default="text"
    )
    note = fields.Html('Description')
    worksheet = fields.Binary('PDF')
    worksheet_google_slide = fields.Char('Google Slide', help="Paste the url of your Google Slide. Make sure the access to the document is public.", tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """ Set reference filed's default value """
        for vals in vals_list:
            if not vals.get('reference') and vals.get('name'):
                vals['reference'] = vals['name']
        return super(MrpOperationTemplate, self).create(vals_list)
    
    def write(self, vals):
        """ If specific fields are updated in the template, the same changes are applied to all linked operations
            that reference this template.
        """
        if vals.get('name'):
            vals['reference'] = vals['name']
        operation_records =self.env['mrp.routing.workcenter'].search([
            ('mrp_operation_temp_id', '=', self.id),
        ])
        for rec in operation_records:
            rec.write({
                'name': vals.get('name') if vals.get('name') else rec.name,
                'workcenter_id': vals.get('work_center_id') if vals.get('work_center_id') else rec.workcenter_id,
                'worksheet_type': vals.get('work_sheet_type') if vals.get('work_sheet_type') else rec.worksheet_type,
                'worksheet': vals.get('worksheet') if vals.get('worksheet') else rec.worksheet,
                'worksheet_google_slide': vals.get('worksheet_google_slide') if vals.get('worksheet_google_slide') else rec.worksheet_google_slide,
                'note': vals.get('note') if vals.get('note') else rec.note,
                })
        return super(MrpOperationTemplate, self).write(vals)
