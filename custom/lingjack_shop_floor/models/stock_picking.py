# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    production_count = fields.Integer(
        groups='')
    
    # Link to Manufacturing Order for pick component transfer notes
    mrp_production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        help='Manufacturing Order this picking is linked to'
    )
    
    # Link to original raw material move
    move_raw_id = fields.Many2one(
        'stock.move',
        string='Raw Material Move',
        help='Original raw material move from manufacturing order'
    )


    def _update_pick_component_state(self):
        """Update pick component transfer note state based on requested quantities"""
        self.ensure_one()
        
        # Remove any pale components from the transfer note
        self._remove_pale_components()
        
        # Check if any moves have requested quantities > 0
        has_requested_quantities = any(move.quantity_requested > 0 for move in self.move_ids)
        
        if has_requested_quantities:
            # Move to 'ready' state when quantities are requested
            if self.state == 'waiting':
                self.state = 'assigned'
                # self.action_assign()
        else:
            # Stay in 'waiting' state when no quantities are requested
            if self.state not in ['done', 'cancel']:
                self.state = 'waiting'
    
    def _remove_pale_components(self):
        """Remove any pale components from this transfer note"""
        self.ensure_one()
        
        # Find pale component moves
        pale_moves = self.move_ids.filtered(lambda m: m.product_id.take_in_pale)
        
        if pale_moves:
            pale_names = ', '.join(pale_moves.mapped('product_id.name'))
            _logger.info(f"Removing pale components from transfer note {self.name}: {pale_names}")
            
            # Cancel and unlink pale component moves
            for move in pale_moves:
                if move.state not in ['done', 'cancel']:
                    move._action_cancel()
                move.unlink()
            
            # Post message to the transfer note
            self.message_post(
                body=_('Pale components removed: %s') % pale_names,
                message_type='notification'
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set initial state for pick component transfer notes"""
        pickings = super().create(vals_list)
        
        for picking in pickings:
            # If this is a pick component transfer note, set initial state
            if (picking.mrp_production_id and 
                picking.picking_type_id.code == 'internal' and  # Assuming pick components use internal transfers
                'Pick Components' in picking.origin):
                picking.state = 'waiting'
        
        return pickings