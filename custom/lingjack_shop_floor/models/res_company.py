# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    shop_floor_component_pick_notify_user_ids = fields.Many2many(
        'hr.employee',
        string='Component Pick Notification Users',
        help='Users who will receive notifications when component pickings are created'
    )
    
    # CS Notification Settings
    enable_cs_mo_confirm_notifications = fields.Boolean(
        string='Enable CS Notifications on MO Confirmation',
        default=True,
        help='Send notifications to CS in-charge when Manufacturing Orders are confirmed'
    )
    
    enable_cs_mo_done_notifications = fields.Boolean(
        string='Enable CS Notifications on MO Completion',
        default=True,
        help='Send notifications to CS in-charge when Manufacturing Orders are completed'
    )
    
    # Auto Lot Generation Settings
    auto_generate_mo_lot_numbers = fields.Boolean(
        string='Auto-Generate Lot Numbers for Manufacturing Orders',
        default=True,
        help='Automatically generate lot/serial numbers for manufactured products when MO is confirmed'
    ) 

    # Component transfer operation type (picking type) for product-triggered picks
    component_transfer_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Component Transfer Operation Type',
        domain="[('code','in',('internal','outgoing','incoming'))]",
        help='Default operation type used when creating component transfer notes from products.'
    )