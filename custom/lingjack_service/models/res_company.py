# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    fsm_control_tag_product_id = fields.Many2one('product.product', string='FSM Control Tag Product')

    
    last_used_qr_sequence = fields.Integer(
        string='Last Used QR Sequence',
        default=1,
        help='Last used sequence number for Service QR codes'
    )

    fsm_bus_servicing_product = fields.Many2one('product.product', string='FSM Bus Servicing Product')

    