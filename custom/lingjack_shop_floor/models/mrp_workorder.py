# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)


class MrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    # Quantity produced as qualified as
    qty_produced = fields.Float(
        'Qualified Quantity', default=0.0,
        readonly=True,
        digits='Product Unit of Measure',
        copy=False,
        help="The number of products already handled by this work order")

    total_produced = fields.Float(
        string='Produced Quantity',
        store=True,
        compute="_compute_qualified_quantities",
        help='Qualified quantity (produced - defects)'
    )

    qty_defects = fields.Float(
        string='Defect Quantity',
        default=0.0,
        digits='Product Unit of Measure',
        help='Quantity of defects during this productivity session'
    )


    # :Lingjack dont need this
    def _set_qty_producing(self):
        return

    @api.depends('name', 'qty_produced')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'{record.name} (Qualified Qty: {record.qty_produced})'


    def action_pick_component(self):
        return self.production_id.action_pick_component()


    def _compute_qualified_quantities(self):
        self.total_produced = 0 # To avoid error, real value will be compute at lingjack work quantities
        return