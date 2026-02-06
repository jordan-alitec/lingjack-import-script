# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fsm_control_tag_product_id = fields.Many2one('product.product', string='FSM Control Tag Product', related='company_id.fsm_control_tag_product_id',readonly=False, help='Product used to tag FSM control items')
    fsm_bus_servicing_product = fields.Many2one('product.product', string='FSM Bus Servicing Product', related='company_id.fsm_bus_servicing_product',readonly=False, help='Product used to tag FSM bus servicing items')