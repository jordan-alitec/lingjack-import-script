from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.http import request
from collections import defaultdict
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    control_tag_count = fields.Integer(
        string='Control Tags',
        compute='_compute_control_tag_count',
    )

    @api.depends('move_line_ids')
    def _compute_control_tag_count(self):
        for picking in self:
            if not self.env.user.has_group('lingjack_service.group_control_tag'):
                picking.control_tag_count = 0
                continue
            if not picking.move_line_ids:
                picking.control_tag_count = 0
                continue
            picking.control_tag_count = self.env['control.tag'].search_count([
                ('move_line_id', 'in', picking.move_line_ids.ids),
            ])

    def action_view_control_tag(self):
        self.ensure_one()
        tags = self.env['control.tag'].search([
            ('move_line_id', 'in', self.move_line_ids.ids),
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Control Tags',
            'res_model': 'control.tag',
            'view_mode': 'list',
            'domain': [('id', 'in', tags.ids)],
            'context': {'default_invoice_id': False, 'default_move_line_id': False},
        }

    fsm_subtask_id = fields.Many2one(
        'project.task',
        string='Task',
        related='group_id.task_id',
        store=True,
        readonly=True,
        help='FSM subtask linked via the procurement group that created this delivery order.',
    )

    fsm_service_location_id = fields.Many2one(
        'stock.location',
        string='Service Location',
        related='fsm_subtask_id.service_location_id',
        store=True,
        readonly=True,
        help="Service location from the FSM task. This is informational and does not change the picking's stock source location.",
    )

    @api.constrains('fsm_service_location_id','picking_type_id')
    def constrains_service_location_id(self):
        for rec in self:
            if rec.fsm_service_location_id:
                rec.location_id = rec.fsm_service_location_id.id

    @api.constrains('sale_id')
    def _update_do_remarks_from_cs_remarks(self):
        """
        Override create to sync CS remarks from parent task to DO remarks
        when delivery order is created
        """
        # Sync CS remarks to DO remarks for newly created delivery orders
        for picking in self:
            if picking.sale_id and picking.picking_type_id.code == 'outgoing':
                # Find parent task linked to the sale order
                parent_task = self.env['project.task'].search([
                    ('sale_order_id', '=', picking.sale_id.id),
                    ('parent_id', '=', False)  # Only parent tasks
                ], limit=1)
                
                if parent_task and parent_task.cs_remarks:
                    
                    picking.do_remarks = parent_task.cs_remarks



    ### Control tag handling
    def action_create_invoice(self):
        res = super(StockPicking, self).action_create_invoice()
        for picking in self:
            if picking.picking_type_id.code == 'outgoing':
                for move in picking.move_ids_without_package:
                    for line in move.move_line_ids:
                        line._create_control_tag(invoice_id=res.id)
        return res