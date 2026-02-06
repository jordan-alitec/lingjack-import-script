from odoo import models, fields, api
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _name = 'service.condition'
    _description = 'Service Condition'

    name = fields.Char(string='Name')
    is_internal = fields.Boolean(string='Internal Service?', default=False)
    sale_type = fields.Many2one(comodel_name='sale.type', string='Sale Type')

    