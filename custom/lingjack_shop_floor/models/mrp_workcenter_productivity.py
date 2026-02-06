# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    quantity_produced = fields.Float(
        string='Quantity Produced',
        default=0.0,
        digits='Product Unit of Measure',
        help='Quantity produced during this productivity session'
    )
    qty_qualified = fields.Float(
        string='Qualified Quantity',
        compute='_compute_qualified_quantity',
        store=False,
        help='Qualified quantity (produced - defects)'
    )

    qty_defects = fields.Float(
        string='Defect Quantity',
        default=0.0,
        digits='Product Unit of Measure',
        help='Quantity of defects during this productivity session'
    )

    notes = fields.Text(
        string='Production Notes',
        help='Additional notes about this production session'
    )

    procurement_group_id = fields.Many2one(related='production_id.procurement_group_id', store=True)

    @api.depends('quantity_produced')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"Done: {record.quantity_produced}"

    @api.constrains('quantity_produced', 'qty_defects')
    def _check_quantities(self):
        for record in self:
            if record.quantity_produced < 0:
                raise ValidationError(_('Quantity produced cannot be negative.'))
            if record.qty_defects < 0:
                raise ValidationError(_('Defect quantity cannot be negative.'))
            if record.qty_defects > record.quantity_produced:
                raise ValidationError(_('Defect quantity cannot exceed quantity produced.'))

    # @api.depends('quantity_produced', 'qty_defects')
    # def _compute_qualified_quantity(self):
    #     """Compute qualified quantity (produced - defects)"""
    #     for record in self:
    #         qualified_qty = record.quantity_produced - record.qty_defects
    #         record.qty_qualified = max(0, qualified_qty)
    #         record.workorder_id._compute_qualified_quantities()


    workorder_operation_name = fields.Char(
        string='Operation Name',
        related='workorder_id.operation_id.name',
        readonly=True,
        help='Name of the operation being performed'
    )

    workorder_scheduled_start = fields.Datetime(
        string='Scheduled Start',
        related='workorder_id.date_start',
        readonly=True,
        help='Scheduled start date of the work order'
    )

    workorder_scheduled_end = fields.Datetime(
        string='Scheduled End',
        related='workorder_id.date_finished',
        readonly=True,
        help='Scheduled end date of the work order'
    )

    has_time_tracking = fields.Boolean(
        string='Has Time Tracking',
        compute='_compute_has_time_tracking',
        store=False,
        help='Indicates if this work order has any time tracking records'
    )

    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        related='workorder_id.production_id',
        readonly=True,
        store=True,
        help='Manufacturing order related to this work order'
    )

    @api.depends('quantity_produced', 'qty_defects')
    def _compute_qualified_quantity(self):

        """Compute qualified quantity (produced - defects)"""
        for record in self:

            # record.workorder_id._compute_qualified_quantities()
            qualified_qty = record.quantity_produced - record.qty_defects
            record.qty_qualified = max(0, qualified_qty)

    @api.depends('workorder_id')
    def _compute_has_time_tracking(self):
        """Compute if work order has time tracking records"""
        for record in self:
            record.has_time_tracking = True

    @api.depends('workorder_id', 'workorder_id.operation_id.name', 'qty_qualified')
    def _compute_gantt_display_name(self):
        """Compute enhanced display name for Gantt view"""
        for record in self:
            if record.workorder_id and record.workorder_id.operation_id:
                operation_name = record.workorder_id.operation_id.name
                if record.qty_qualified > 0:
                    record.gantt_display_name = f"{operation_name} - Qty: {record.qty_qualified}"
                else:
                    record.gantt_display_name = operation_name
            elif record.workorder_id:
                workorder_name = record.workorder_id.name
                if record.qty_qualified > 0:
                    record.gantt_display_name = f"{workorder_name} - Qty: {record.qty_qualified}"
                else:
                    record.gantt_display_name = workorder_name
            else:
                record.gantt_display_name = _('Productivity Session')

    @api.model
    def _search_include_workorders_without_tracking(self, operator, value):
        """Custom search method to include work orders without time tracking"""
        if value and operator == '=':
            workorders_with_tracking = self.search([]).mapped('workorder_id')
            all_workorders = self.env['mrp.workorder'].search([])
            workorders_without_tracking = all_workorders - workorders_with_tracking

            virtual_records = []
            for wo in workorders_without_tracking:
                if wo.date_planned_start:
                    virtual_records.append({
                        'id': f'virtual_{wo.id}',
                        'workorder_id': wo,
                        'date_start': wo.date_planned_start,
                        'date_end': wo.date_planned_finished or wo.date_planned_start + timedelta(hours=1),
                        'gantt_display_name': f"{wo.operation_id.name if wo.operation_id else wo.name} - No Tracking",
                        'has_time_tracking': False,
                    })

            return [('id', 'in', self.search([]).ids + [f'virtual_{wo.id}' for wo in workorders_without_tracking])]

        return [('id', 'in', [])]

