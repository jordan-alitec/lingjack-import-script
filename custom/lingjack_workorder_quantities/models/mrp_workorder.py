# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import float_round
import logging


_logger = logging.getLogger(__name__)

class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    residual_qty_produced = fields.Float(
        string='Previous Produced Qty',
        help='Quantity produced in previous MO that can be used in this workorder',
        default=0.0,
        copy=False
    )

    residual_qty_defects = fields.Float(
        string='Residual Defect Qty',
        help='Quantity of defects from previous MO carried over to this workorder',
        default=0.0,
        copy=False
    )

    qty_qualified_current_session = fields.Float(
        string='Produced Quantity',
        default=0.0,
        compute="_compute_qty_qualified",
        digits='Product Unit of Measure',
        help='Quantity of qualified during this productivity session'
    )


    def _compute_qty_qualified(self):
        for rec in self:
            rec.qty_qualified_current_session = max(rec.qty_produced - rec.residual_qty_produced, 0)



    @api.depends('qty_production', 'qty_produced', 'qty_defects', 'production_id.product_uom_id',
                 'residual_qty_produced', 'residual_qty_defects')
    def _compute_qty_remaining(self):
        """Override to properly compute remaining quantities including residuals"""
        for wo in self:
            if wo.production_id.product_uom_id:
                # Consider both current and residual quantities
                total_produced = wo.total_produced
                total_defects = wo.qty_defects + wo.residual_qty_defects
                total_qualified = total_produced - total_defects
                wo.qty_remaining = max(
                    float_round(
                        wo.qty_production - total_qualified,
                        precision_rounding=wo.production_id.product_uom_id.rounding
                    ),
                    0
                )
            else:
                wo.qty_remaining = 0

    @api.depends('time_ids.quantity_produced', 'time_ids.qty_defects', 'residual_qty_produced')
    def _compute_qualified_quantities(self):
        """Compute qualified quantities and defects including residuals"""
        for record in self:
            # Get quantities from time tracking
            total_produced = sum(record.time_ids.mapped('quantity_produced'))
            total_defects = sum(record.time_ids.mapped('qty_defects'))

            # Add residual quantities
            total_produced += record.residual_qty_produced
            # total_defects += record.residual_qty_defects


            qualified_qty = total_produced - total_defects

            record.qty_defects = total_defects
            record.qty_produced = max(0, qualified_qty)
            record.total_produced = total_produced

            record.production_id._compute_qualified_quantities()

    def _prepare_backorder_workorder_vals(self):
        """Prepare values for workorder in backorder"""
        vals = super()._prepare_backorder_workorder_vals()

        # Reset quantity fields for the backorder workorder
        vals.update({
            'total_produced': 0,
            'qty_produced': 0,
            'qty_defects': 0,
        })

        return vals




    def _get_duration_expected(self, alternative_workcenter=False):
        """Override to adjust expected duration based on remaining quantities"""
        duration = super()._get_duration_expected(alternative_workcenter=alternative_workcenter)

        if self.qty_production and self.qty_remaining:
            # Adjust duration based on remaining quantity ratio
            ratio = self.qty_remaining / self.qty_production
            duration = duration * ratio

        return duration 