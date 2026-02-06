# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def button_validate(self):
        """Override to update SWO line qty_in_stock when SFP transfer is done"""
        result = super().button_validate()
        
        # Check if this is an SFP transfer and update SWO line quantities
        for rec in self:
            if rec.state == 'done':
                # Find SFP distributions linked to this picking
                distributions = self.env['mrp.production.sfp.distribution'].search([
                    ('picking_id', '=', rec.id)
                ])
                
                for distribution in distributions:
                    distribution._on_picking_done(rec)
        
        return result
