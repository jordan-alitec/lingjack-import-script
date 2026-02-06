# -*- coding: utf-8 -*-
# imports of odoo
from odoo import models, fields, api

class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'
    _order = 'urgency_level asc'

    urgency = fields.Selection(related='production_id.urgency', string="Urgency")
    urgency_level = fields.Integer(string="Urgency Level", compute='_compute_urgency_level', store=True)

    @api.depends('urgency')
    def _compute_urgency_level(self):
        urgency_map = {
            'low_priority': 1,
            'normal': 2,
            'high': 3,
            'urgent': 4,
        }
        for record in self:
            record.urgency_level = urgency_map.get(record.urgency, 0)