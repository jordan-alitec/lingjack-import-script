from odoo import models, fields


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    task_id = fields.Many2one(
        'project.task',
        string='FSM Task/Subtask',
        index=True,
        help='When set, this procurement group (and its pickings) is dedicated to a specific FSM subtask.',
    )

