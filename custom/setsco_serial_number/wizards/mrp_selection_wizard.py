from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MrpSelectionWizard(models.TransientModel):
    _name = 'mrp.selection.wizard'
    _description = 'Manufacturing Order Selection Wizard'

    production_id = fields.Many2one(
        'mrp.production', 
        string='Manufacturing Order', 
        required=True,
        domain=[('state', 'in', ['confirmed', 'progress', 'to_close']),('requires_setsco_serials','=',True)]
    )
    
    product_id = fields.Many2one(
        'product.product', 
        string='Product', 
        related='production_id.product_id', 
        readonly=True
    )
    
    product_qty = fields.Float(
        string='Quantity to Produce', 
        related='production_id.product_qty',
        digits='Product Unit of Measure',
        readonly=True
    )
    
    setsco_serial_count = fields.Integer(
        string='Assigned Setsco Serials',
        related='production_id.setsco_serial_count',
        readonly=True
    )
    
    remaining_qty = fields.Float(
        string='Remaining Quantity',
        digits='Product Unit of Measure',
        compute='_compute_remaining_qty'
    )
    
    can_assign_serials = fields.Boolean(
        string='Can Assign More Serials',
        compute='_compute_can_assign_serials'
    )

    @api.depends('product_qty', 'setsco_serial_count')
    def _compute_remaining_qty(self):
        for wizard in self:
            wizard.remaining_qty = wizard.product_qty - wizard.setsco_serial_count

    @api.depends('remaining_qty')
    def _compute_can_assign_serials(self):
        for wizard in self:
            wizard.can_assign_serials = wizard.remaining_qty > 0

    def action_assign_setsco_serials(self):
        """Call the action_assign_setsco_serials method of the selected manufacturing order"""
        self.ensure_one()
        if not self.production_id:
            raise ValidationError(_('Please select a manufacturing order first.'))
        
        return self.production_id.action_assign_setsco_serials()