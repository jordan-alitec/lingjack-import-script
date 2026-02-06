# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class PreviousTransferSearchWizard(models.TransientModel):
    """Wizard to search stock pickings by previous transfer number"""
    _name = 'previous.transfer.search.wizard'
    _description = 'Previous Transfer Search Wizard'

    previous_transfer = fields.Char(
        string='Previous Transfer Number',
        help='Enter previous transfer number or scan barcode'
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Found Transfer',
        readonly=True
    )
    picking_info = fields.Html(
        string='Transfer Information',
        compute='_compute_picking_info',
        store=False
    )

    @api.depends('picking_id')
    def _compute_picking_info(self):
        """Display transfer information when found"""
        for wizard in self:
            if wizard.picking_id:
                picking = wizard.picking_id
                wizard.picking_info = f"""
                    <div class="alert alert-success">
                        <h4><i class="fa fa-check-circle"></i> Transfer Found</h4>
                        <p><strong>Name:</strong> {picking.name}</p>
                        <p><strong>Type:</strong> {picking.picking_type_id.name}</p>
                        <p><strong>Partner:</strong> {picking.partner_id.name if picking.partner_id else 'N/A'}</p>
                        <p><strong>Previous Transfer:</strong> {picking.previous_transfer if picking.previous_transfer else 'N/A'}</p>
                        <p><strong>State:</strong> {picking.state}</p>
                        <p><strong>Scheduled Date:</strong> {picking.scheduled_date if picking.scheduled_date else 'N/A'}</p>
                    </div>
                """
            else:
                wizard.picking_info = False

    def action_search(self):
        """Search for transfer by previous_transfer field"""
        self.ensure_one()
        if not self.previous_transfer:
            raise UserError('Please enter a previous transfer number')

        # Search for picking by previous_transfer field
        picking = self.env['stock.picking'].search([
            ('previous_transfer', 'ilike', self.previous_transfer.strip())
        ], limit=1)

        if picking:
            self.picking_id = picking
            # Return action to reload wizard and show transfer info
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'previous.transfer.search.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            raise UserError(f'No transfer found with previous transfer: {self.previous_transfer}')

    def action_open_picking(self):
        """Open the found transfer in form view"""
        self.ensure_one()
        if not self.picking_id:
            raise UserError('No transfer selected')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_scan_barcode(self):
        """Trigger camera barcode scanner"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'previous_transfer_barcode_scanner',
            'params': {
                'wizard_id': self.id,
                'model': 'previous.transfer.search.wizard',
            }
        }

