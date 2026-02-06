# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import float_round
import json
import logging
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # Transient field to store workorder quantities temporarily during backorder creation
    original_wo_quantities = fields.Text(
        string='Original Workorder Quantities',
        help='Technical field to store original workorder quantities during backorder creation',
        copy=False
    )

    def _get_backorder_mo_vals(self):
        """Override to properly handle workorder quantities in backorder"""
        vals = super()._get_backorder_mo_vals()

        # Store the original workorder quantities as a string representation
        if self.workorder_ids:
            wo_quantities = {
                str(wo.operation_id.id): {
                    'total_produced': wo.total_produced,
                    'qty_produced': wo.qty_produced,
                    'qty_defects': wo.qty_defects,
                } for wo in self.workorder_ids
            }
            vals['original_wo_quantities'] = str(wo_quantities)

        return vals

    def _split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False):
        """Override to handle workorder quantities during split"""
        # Store the workorder quantities before split
        wo_quantities = {}
        for wo in self.workorder_ids:
            wo_quantities[wo.operation_id.id] = {
                'total_produced': wo.total_produced,
                'qty_produced': wo.qty_produced,
                'qty_defects': wo.qty_defects,
                'id': wo.id,
            }

            wo.qty_reported_from_previous_wo = 0

        # Perform the standard split
        backorders = super()._split_productions(amounts=amounts,
                                                cancel_remaining_qty=cancel_remaining_qty,
                                                set_consumed_qty=set_consumed_qty)

        if not backorders or not self.workorder_ids:
            return backorders

        # Get the minimum qualified quantity across all workorders
        min_qualified = min(wo.qty_produced for wo in self.workorder_ids)

        # For each backorder, set residual quantities
        for backorder in backorders:
            self._set_backorder_residual_quantities(backorder, wo_quantities, min_qualified)

            # if backorder.state not in ['done','cancel']:
            #     backorder.is_planned = True
            #     backorder.action_generate_serial()


        return backorders

    def _set_backorder_residual_quantities(self, backorder, wo_quantities, completed_qty):
        """Set residual quantities for backorder workorders"""
        for wo in backorder.workorder_ids:
            if wo.operation_id.id not in wo_quantities or wo.state == 'done':
                continue

            original_quantities = wo_quantities[wo.operation_id.id]

            # Calculate residual quantities
            # Any quantity that was produced beyond what was completed in this batch
            # becomes residual for the next workorder
            residual_produced = max(0, original_quantities['qty_produced'] - completed_qty)
            residual_defects = max(0, original_quantities['qty_defects'])
            wo.write({
                'residual_qty_produced': residual_produced,
                'residual_qty_defects': 0,
                'qty_reported_from_previous_wo': 0,
            })

            wo.qty_remaining

            #       Tie the unclose time session to the new backorder workorder
            ongoing_session = self.env['mrp.workcenter.productivity'].sudo().search(
                [('workorder_id', '=', original_quantities['id']), ('backorder_move', '=', True)])
            if ongoing_session:
                ongoing_session.write({
                    'workorder_id': wo.id,
                    'date_end': False,
                    'backorder_move': False,
                })
                wo.production_id.action_start()
                wo.write({
                    'state': 'progress',
                    'employee_ids': [(6,0, ongoing_session.employee_id.ids)],
                })


    def _create_backorder_time_records(self, backorder, wo_time_records, completed_qty):
        """Create appropriate time tracking records for backorder workorders"""
        # Get the productive loss type (required for time tracking)
        productive_loss = self.env['mrp.workcenter.productivity.loss'].search(
            [('loss_type', '=', 'productive')], limit=1)

        if not productive_loss:
            # If no productive loss type exists, create one
            productive_loss = self.env['mrp.workcenter.productivity.loss'].create({
                'name': 'Productive Time',
                'loss_type': 'productive',
                'manual': True
            })

        for wo in backorder.workorder_ids:
            if wo.operation_id.id not in wo_time_records:
                continue

            original_records = wo_time_records[wo.operation_id.id]
            remaining_produced = max(0, original_records['total_produced'] - completed_qty)
            remaining_defects = max(0, original_records['total_defects'])

            if remaining_produced > 0:
                # Create a new time tracking record for the remaining quantity
                self.env['mrp.workcenter.productivity'].create({
                    'workorder_id': wo.id,
                    'workcenter_id': wo.workcenter_id.id,
                    'date_start': fields.Datetime.now(),
                    'date_end': fields.Datetime.now(),
                    'loss_id': productive_loss.id,  # Required field
                    'quantity_produced': remaining_produced,
                    'qty_defects': remaining_defects,
                    'description': _('Transferred from original work order')
                })

    def pre_button_mark_done(self):
        """Pre-validation before marking production as done"""
        # Validate setsco serial count before marking done
        for rec in self:
            if rec.workorder_ids:
                rec.workorder_ids.time_ids.filtered(lambda w: w.date_end == False).write({
                    'backorder_move': True,
                })
        return super().pre_button_mark_done()

    def _adjust_backorder_workorder_quantities(self, backorder):
        """Adjust workorder quantities in backorder based on original progress"""
        try:
            # Safely evaluate the string representation back to a dictionary
            original_quantities = eval(backorder.original_wo_quantities or '{}')
        except Exception:
            original_quantities = {}

        for wo in backorder.workorder_ids:
            if str(wo.operation_id.id) in original_quantities:
                orig_qty = original_quantities[str(wo.operation_id.id)]

                # Calculate the actual remaining quantity for this operation
                total_to_produce = self.product_qty
                already_produced = orig_qty.get('total_produced', 0)
                already_qualified = orig_qty.get('qty_produced', 0)

                # Set the correct quantities for backorder workorder
                wo.write({
                    'qty_production': backorder.product_qty,
                    'total_produced': 0,
                    'qty_produced': 0,  # Reset for the backorder
                    'qty_defects': 0,  # Reset for the backorder
                    'qty_remaining': backorder.product_qty
                })

    def _get_quantity_to_backorder(self):
        """Override to determine correct backorder quantity based on workorder progress"""
        self.ensure_one()

        if not self.workorder_ids:
            return super()._get_quantity_to_backorder()

        # Get the minimum qualified quantity across all workorders
        min_qualified = min(wo.qty_produced for wo in self.workorder_ids)

        # The backorder quantity should be the original quantity minus what was actually completed
        backorder_qty = self.product_qty - min_qualified

        return backorder_qty if backorder_qty > 0 else 0 