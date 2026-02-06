# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShopFloorQuantityPopup(models.TransientModel):
    _name = 'shop.floor.quantity.popup'
    _description = 'Shop Floor Quantity Entry Popup'

    productivity_id = fields.Many2one(
        'mrp.workcenter.productivity',
        string='Productivity Record',
        required=True
    )

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        related='productivity_id.workorder_id',
        readonly=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='workorder_id.product_id',
        readonly=True
    )

    quantity_produced = fields.Float(
        string='Quantity Produced',
        digits='Product Unit of Measure',
        required=True,
        default=1.0
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True
    )

    qty_defects = fields.Float(
        string='Defect Quantity',
        digits='Product Unit of Measure',
        default=0.0
    )

    qty_qualified = fields.Float(
        string='Qualified Quantity',
        compute='_compute_qualified_quantity',
        store=False,
        help='Qualified quantity (produced - defects)'
    )

    notes = fields.Text(string='Production Notes')

    continue_to_pending = fields.Boolean(
        string='Pause Session After Save',
        help='If checked, the session will be paused after saving the quantity',
        default=False
    )

    quality_check = fields.Boolean(
        string='Quality Check Completed',
        help='Confirm that quality check has been performed on the produced items',
        default=False
    )

    @api.depends('quantity_produced', 'qty_defects')
    def _compute_qualified_quantity(self):
        """Compute qualified quantity (produced - defects)"""
        for record in self:
            qualified_qty = record.quantity_produced - record.qty_defects
            record.qty_qualified = max(0, qualified_qty)

    @api.constrains('quantity_produced', 'qty_defects')
    def _check_quantities(self):
        for record in self:
            if record.quantity_produced < 0:
                raise ValidationError(_('Quantity produced cannot be negative.'))
            if record.qty_defects < 0:
                raise ValidationError(_('Defect quantity cannot be negative.'))
            if record.qty_defects > record.quantity_produced:
                raise ValidationError(_('Defect quantity cannot be greater than quantity produced.'))

    def action_save_quantity(self):
        """Save the quantity and close all concurrent sessions for the same workorder"""
        self.ensure_one()

        # Validate that quality check is completed before saving
        if not self.quality_check:
            raise ValidationError(
                _('Quality check must be completed before saving the quantity. Please check the "Quality Check Completed" box.'))

        # Find all active productivity sessions for the same workorder
        concurrent_sessions = self.env['mrp.workcenter.productivity'].search([
            ('workorder_id', '=', self.workorder_id.id),
            ('date_end', '=', False),  # Active sessions (not yet closed)
            ('id', '!=', self.productivity_id.id)  # Exclude current session
        ])

        # Calculate total quantity to distribute among all sessions
        total_quantity = self.quantity_produced
        total_defects = self.qty_defects
        total_sessions = len(concurrent_sessions) + 1  # +1 for current session
        
        # Calculate base quantity per session (integer division)
        base_qty_per_session = int(total_quantity // total_sessions)
        base_defects_per_session = int(total_defects // total_sessions)
        
        # Calculate remainder (undividable amount)
        qty_remainder = total_quantity - (base_qty_per_session * total_sessions)
        defects_remainder = total_defects - (base_defects_per_session * total_sessions)

        # Update current productivity record with quantities (gets remainder)
        current_qty = base_qty_per_session + qty_remainder
        current_defects = base_defects_per_session + defects_remainder
        
        productivity_vals = {
            'quantity_produced': current_qty,
            'qty_qualified': current_qty,
            'qty_defects': current_defects,
            'notes': self.notes or '',
            'date_end': fields.Datetime.now()
        }
        self.productivity_id.write(productivity_vals)

        # Update all concurrent sessions with distributed quantities
        for session in concurrent_sessions:
            session_vals = {
                'quantity_produced': base_qty_per_session,
                'qty_qualified': base_qty_per_session,
                'qty_defects': base_defects_per_session,
                'notes': f'Quantity distributed from concurrent session (Employee: {self.employee_id.name if self.employee_id else "Unknown"})',
                'date_end': fields.Datetime.now()
            }
            session.write(session_vals)

        # Set workorder to pending state
        self.workorder_id.with_context(skip_popup=True).button_pending()
        self.workorder_id.employee_ids = [(6, 0, [])]
        # Prepare notification message
        if concurrent_sessions:
            session_count = len(concurrent_sessions) + 1
            message = _('Quantity saved and %d concurrent sessions completed successfully. Total quantity: %.2f distributed among %d employees.') % (
                session_count, total_quantity, session_count)
        else:
            message = _('Quantity saved and session completed successfully.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Session Completed'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }