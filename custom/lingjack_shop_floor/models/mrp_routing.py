# -*- coding: utf-8 -*-
#import of odoo
from odoo import api, fields, models

class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'
    
    mrp_operation_temp_id = fields.Many2one("mrp.operation.template", string='Operation Template')
    
    @api.onchange('mrp_operation_temp_id')
    def _onchange_mrp_operation_temp(self):
        """ If Operation template selected automatically populate the fields (name,workcenter_id,worksheet_type,worksheet,worksheet_google_slide,note) values 
            from the selected template 
        """
        self.write({
            'name': self.mrp_operation_temp_id.name,
            'workcenter_id': self.mrp_operation_temp_id.work_center_id,
            'worksheet_type': self.mrp_operation_temp_id.work_sheet_type,
            'worksheet':self.mrp_operation_temp_id.worksheet if self.mrp_operation_temp_id.worksheet else False,
            'worksheet_google_slide': self.mrp_operation_temp_id.worksheet_google_slide if self.mrp_operation_temp_id.worksheet_google_slide else False,
            'note': self.mrp_operation_temp_id.note if self.mrp_operation_temp_id.note else False
            })
