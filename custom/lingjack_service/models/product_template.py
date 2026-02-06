from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression

from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_always_show = fields.Boolean(string='Always Show in Service', default=False)
    is_control_tag = fields.Boolean(string='Is Control Tag', default=False)
