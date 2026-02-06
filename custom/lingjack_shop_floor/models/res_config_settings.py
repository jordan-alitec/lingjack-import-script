# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shop_floor_component_pick_notify_user_ids = fields.Many2many(
        'hr.employee',
        'shop_floor_component_pick_notify_rel',
        'config_id',
        'user_id',
        string='Users to Notify on Component Pick',
        help='Users who will receive notifications when component picking is created for manufacturing orders',
        related='company_id.shop_floor_component_pick_notify_user_ids',
        readonly=False
    )
    
    # CS Notification Settings
    enable_cs_mo_confirm_notifications = fields.Boolean(
        string='CS Notifications: MO Confirmation',
        help='Send notifications to CS in-charge when Manufacturing Orders are confirmed',
        related='company_id.enable_cs_mo_confirm_notifications',
        readonly=False
    )
    
    enable_cs_mo_done_notifications = fields.Boolean(
        string='CS Notifications: MO Completion',
        help='Send notifications to CS in-charge when Manufacturing Orders are completed',
        related='company_id.enable_cs_mo_done_notifications',
        readonly=False
    )
    
    auto_generate_mo_lot_numbers = fields.Boolean(
        string='Auto-Generate MO Lot Numbers',
        help='Automatically generate lot/serial numbers for manufactured products when MO is confirmed',
        related='company_id.auto_generate_mo_lot_numbers',
        readonly=False
    )

    component_transfer_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Component Transfer Operation Type',
        related='company_id.component_transfer_picking_type_id',
        readonly=False,
        help='Default operation type used when creating component transfer notes from products.'
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        
        # Get the users from company settings
        res['shop_floor_component_pick_notify_user_ids'] = [(6, 0, company.shop_floor_component_pick_notify_user_ids.ids)]
        if company.component_transfer_picking_type_id:
            res['component_transfer_picking_type_id'] = company.component_transfer_picking_type_id.id
            
        return res

    def set_values(self):
        super().set_values()
        company = self.env.company
        
        # Update the company field with the selected users
        company.shop_floor_component_pick_notify_user_ids = self.shop_floor_component_pick_notify_user_ids 
        company.component_transfer_picking_type_id = self.component_transfer_picking_type_id