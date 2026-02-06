# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShopFloorComponentTransferNote(models.Model):
    _name = 'shop.floor.component.transfer.note'
    _description = 'Shop Floor Component Transfer Note'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Transfer Note Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',

    )
    
    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',

    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', readonly=True, tracking=True)
    
    transfer_date = fields.Datetime(
        string='Transfer Date',
        default=fields.Datetime.now,

    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,

    )
    
    line_ids = fields.One2many(
        'shop.floor.component.transfer.line',
        'transfer_note_id',
        string='Transfer Lines',
    )
    
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('shop.floor.component.transfer.note') or _('New')
        return super().create(vals)

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self.message_post(body=_('Transfer note confirmed.'))

    def action_done(self):
        # Validate that all lines have quantities transferred
        for line in self.line_ids:
            if line.quantity_transferred <= 0:
                raise UserError(_('All transfer lines must have quantity transferred greater than 0.'))
        
        # Here you could implement actual stock moves if needed
        # For now, we just mark as done
        self.write({'state': 'done'})
        self.message_post(body=_('Transfer note completed. All components transferred.'))

    def action_cancel(self):
        if self.state == 'done':
            raise UserError(_('Cannot cancel a completed transfer note.'))
        self.write({'state': 'cancel'})
        self.message_post(body=_('Transfer note cancelled.'))


class ShopFloorComponentTransferLine(models.Model):
    _name = 'shop.floor.component.transfer.line'
    _description = 'Shop Floor Component Transfer Line'

    transfer_note_id = fields.Many2one(
        'shop.floor.component.transfer.note',
        string='Transfer Note',
        required=True,
        ondelete='cascade'
    )
    
    move_id = fields.Many2one(
        'stock.move',
        string='Original Stock Move',
        readonly=True
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        readonly=True
    )
    
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        readonly=True
    )
    
    quantity_requested = fields.Float(
        string='Quantity Requested',
        required=True,
        readonly=True
    )
    
    quantity_transferred = fields.Float(
        string='Quantity Transferred',
        default=0.0
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        readonly=True
    )
    
    location_src_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        readonly=True
    )
    
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        readonly=True
    )
    
    notes = fields.Text(string='Line Notes')

    @api.constrains('quantity_transferred', 'quantity_requested')
    def _check_quantity_transferred(self):
        for line in self:
            if line.quantity_transferred < 0:
                raise ValidationError(_('Quantity transferred cannot be negative.'))
            if line.quantity_transferred > line.quantity_requested:
                raise ValidationError(_('Cannot transfer more than requested quantity for %s.') % line.product_id.name)


class ShopFloorComponentPickerWizard(models.TransientModel):
    _name = 'shop.floor.component.picker.wizard'
    _description = 'Shop Floor Component Picker Wizard'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        required=True,
        readonly=True
    )
    
    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',
        readonly=True
    )
    
    picker_line_ids = fields.One2many(
        'shop.floor.component.picker.line',
        'picker_id',
        string='Components to Pick'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if 'workorder_id' in self.env.context:
            workorder_id = self.env.context['workorder_id']
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            
            res['workorder_id'] = workorder.id
            res['production_id'] = workorder.production_id.id
            
            # Get components for this work order
            component_moves = workorder.move_raw_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty > 0
            )
            
            if component_moves:
                # Create lines for each component
                line_vals = []
                for move in component_moves:
                    # Calculate remaining quantity (total required - already consumed)
                    remaining_qty = move.product_uom_qty - move.quantity
                    
                    # Only add components that still have remaining quantity to pick
                    if remaining_qty > 0:
                        line_vals.append((0, 0, {
                            'source_move_id': move.id,  # Store move ID as integer
                            'product_id': move.product_id.id,
                            'available_quantity': remaining_qty,  # Show remaining quantity as available
                            'quantity_to_pick': remaining_qty,  # Default to remaining quantity
                            'uom_id': move.product_uom.id,
                            'location_src_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                        }))
                res['picker_line_ids'] = line_vals
        
        return res

    def action_pick_components(self):
        """Create transfer note instead of updating stock moves"""
        self.ensure_one()
        
        # Validate that at least one component has quantity > 0
        lines_to_pick = self.picker_line_ids.filtered(lambda l: l.quantity_to_pick > 0)
        if not lines_to_pick:
            raise UserError(_('Please specify quantity to pick for at least one component.'))
        
        # Create transfer note
        transfer_note_vals = {
            'workorder_id': self.workorder_id.id,
            'production_id': self.production_id.id,
            'state': 'confirmed',  # Start in confirmed state as requested
            'notes': _('Created from component picker for work order %s') % self.workorder_id.name,
        }
        
        transfer_note = self.env['shop.floor.component.transfer.note'].create(transfer_note_vals)
        
        # Create transfer lines
        for line in lines_to_pick:
            # Validate source move still exists
            if not line.source_move_id:
                raise UserError(_('Invalid source move reference for product %s') % line.product_id.name)
                
            source_move = self.env['stock.move'].browse(line.source_move_id)
            if not source_move.exists():
                raise UserError(_('Source move no longer exists for product %s') % line.product_id.name)
            
            transfer_line_vals = {
                'transfer_note_id': transfer_note.id,
                'move_id': source_move.id,
                'product_id': line.product_id.id,
                'workorder_id': self.workorder_id.id,
                'quantity_requested': line.quantity_to_pick,
                'quantity_transferred': line.quantity_to_pick,  # Assume fully transferred for now
                'uom_id': line.uom_id.id,
                'location_src_id': line.location_src_id.id,
                'location_dest_id': line.location_dest_id.id,
            }
            self.env['shop.floor.component.transfer.line'].create(transfer_line_vals)
        
        # Log the creation
        _logger.info(f"[Shop Floor] Created transfer note {transfer_note.name} for workorder {self.workorder_id.name} with {len(lines_to_pick)} lines")
        
        # Return success message and option to view the transfer note
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transfer Note Created'),
                'message': _('Component Transfer Note %s has been created in confirmed state with %d components for work order %s.') % (
                    transfer_note.name, len(lines_to_pick), self.workorder_id.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }


class ShopFloorComponentPickerLine(models.TransientModel):
    _name = 'shop.floor.component.picker.line'
    _description = 'Shop Floor Component Picker Line'

    picker_id = fields.Many2one(
        'shop.floor.component.picker.wizard',
        string='Picker',
        required=True,
        ondelete='cascade'
    )
    
    # Store move reference for transfer note creation but don't display
    source_move_id = fields.Integer(
        string='Source Move ID',
        help='Reference to original stock move for transfer note creation'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True
    )
    
    quantity_to_pick = fields.Float(
        string='Quantity to Pick',
        required=True
    )
    
    available_quantity = fields.Float(
        string='Available Quantity',
        readonly=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        readonly=True
    )
    
    location_src_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        readonly=True
    )
    
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        readonly=True
    )

    @api.constrains('quantity_to_pick', 'available_quantity', 'source_move_id')
    def _check_quantity_to_pick(self):
        for line in self:
            if line.quantity_to_pick < 0:
                raise ValidationError(_('Quantity to pick cannot be negative.'))
            if line.quantity_to_pick > line.available_quantity:
                raise ValidationError(_('Cannot pick more than available quantity for %s.') % line.product_id.name)
            if not line.source_move_id:
                raise ValidationError(_('Missing source move reference for %s.') % line.product_id.name) 