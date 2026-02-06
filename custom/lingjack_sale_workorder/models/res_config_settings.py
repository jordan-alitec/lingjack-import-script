# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    auto_create_sfp_distribution = fields.Boolean(
        string='Auto-Create SFP Distribution',
        default=True,
        help='Automatically create SFP distribution plan when MO is confirmed'
    )
    
    auto_distribute_excess = fields.Boolean(
        string='Auto-Distribute Excess Production',
        default=True,
        help='Automatically distribute excess production to default SFP location'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    auto_create_sfp_distribution = fields.Boolean(
        string='Auto-Create SFP Distribution',
        help='Automatically create SFP distribution plan when MO is confirmed',
        related='company_id.auto_create_sfp_distribution',
        readonly=False
    )
    
    auto_distribute_excess = fields.Boolean(
        string='Auto-Distribute Excess Production',
        help='Automatically distribute excess production to default SFP location',
        related='company_id.auto_distribute_excess',
        readonly=False
    )
