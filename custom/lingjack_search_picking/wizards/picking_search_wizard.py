# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class PickingSearchWizard(models.TransientModel):
    """Wizard to search stock pickings by barcode scanning or manual input"""
    _name = 'picking.search.wizard'
    _description = 'Picking Search Wizard'

    picking_name = fields.Char(
        string='Picking Number',
        help='Enter picking number or scan barcode'
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Found Picking',
        readonly=True
    )
    picking_info = fields.Html(
        string='Picking Information',
        compute='_compute_picking_info',
        store=False
    )

    @api.depends('picking_id')
    def _compute_picking_info(self):
        """Display picking information when found"""
        for wizard in self:
            if wizard.picking_id:
                picking = wizard.picking_id
                wizard.picking_info = f"""
                    <div class="alert alert-success">
                        <h4><i class="fa fa-check-circle"></i> Picking Found</h4>
                        <p><strong>Name:</strong> {picking.name}</p>
                        <p><strong>Type:</strong> {picking.picking_type_id.name}</p>
                        <p><strong>Partner:</strong> {picking.partner_id.name if picking.partner_id else 'N/A'}</p>
                        <p><strong>State:</strong> {picking.state}</p>
                        <p><strong>Scheduled Date:</strong> {picking.scheduled_date if picking.scheduled_date else 'N/A'}</p>
                    </div>
                """
            else:
                wizard.picking_info = False

    def action_search(self):
        """Search for picking by name"""
        self.ensure_one()
        if not self.picking_name:
            raise UserError('Please enter a picking number')

        # Search for picking (case insensitive)
        picking = self.env['stock.picking'].search([
            ('name', 'ilike', self.picking_name.strip())
        ], limit=1)

        if picking:
            self.picking_id = picking
            # Return action to reload wizard and show picking info
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'picking.search.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            raise UserError(f'No picking found with number: {self.picking_name}')

    def action_open_picking(self):
        """Open the found picking in form view"""
        self.ensure_one()
        if not self.picking_id:
            raise UserError('No picking selected')

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
            'tag': 'picking_barcode_scanner',
            'params': {
                'wizard_id': self.id,
                'model': 'picking.search.wizard',
            }
        }

