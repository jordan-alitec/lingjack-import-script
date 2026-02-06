from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.http import request
from collections import defaultdict
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class SaleLot(models.Model):
    _inherit = 'stock.lot'

    sale_order_line_control_tag_id = fields.Many2one(comodel_name='sale.order.line', string='Sale Order Line Control Tag')