# -*- coding: utf-8 -*-
# Part of Softhealer Technologies
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    backdate_for_inventory_adj = fields.Boolean(
        "Enable Backdate for Inventory Adjustment")
    remark_for_inventory_adj = fields.Boolean("Enable Remark for Adjustment")
    remark_mandatory_for_inventory_adj = fields.Boolean(
        "Remark Mandatory for Adjustment")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    backdate_for_inventory_adj = fields.Boolean(
        related="company_id.backdate_for_inventory_adj", readonly=False)
    remark_for_inventory_adj = fields.Boolean(
        related="company_id.remark_for_inventory_adj", readonly=False)
    remark_mandatory_for_inventory_adj = fields.Boolean(
        related="company_id.remark_mandatory_for_inventory_adj", readonly=False)
