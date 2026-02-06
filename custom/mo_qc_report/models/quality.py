# -*- coding: utf-8 -*-
from odoo import models, fields, api

class QualityPoint(models.Model):
    _inherit = 'quality.point'

    show_in_quality_module = fields.Boolean(
        string="Show in Quality Module",
        default=False,
        help="If checked, this quality control point will be visible in the quality module"
    )

    @api.onchange('operation_id')
    def _onchange_operation_id(self):
        """Set show_in_quality_module to True when operation_id is set"""
        if self.operation_id:
            self.show_in_quality_module = True
        else:
            self.show_in_quality_module = False

class QualityCheck(models.Model):
    _inherit = 'quality.check'

    show_in_quality_module = fields.Boolean(
        string="Show in Quality Module",
        related='point_id.show_in_quality_module',
        readonly=True,
        store=True,
        help="If checked, this quality check will be visible in the quality module"
    ) 