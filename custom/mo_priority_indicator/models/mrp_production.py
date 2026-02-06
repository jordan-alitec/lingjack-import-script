# -*- coding: utf-8 -*-
# imports of odoo
from odoo import models, fields

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    urgency = fields.Selection([
        ('low_priority', 'Low Priority'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')],
        string="Urgency", default='low_priority', required=True)

    def action_open_work_orders(self):
        """ Method to open the Gantt view of Work orders related to the current MO """
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.action_mrp_workorder_workcenter")
        action.update({
            'view_mode': 'gantt',
            'domain': [('id', 'in', self.workorder_ids.ids)]
            })
        return action
