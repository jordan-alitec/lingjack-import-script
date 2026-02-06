# -*- coding: utf-8 -*-

# from typing import Required
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class SetscoInternalCompanyReceiveWizard(models.TransientModel):
    """Wizard to mark serials received from an internal company back to LJE.

    This sets the serials to Finished Goods and clears transient transfer flags.
    """
    _name = 'setsco.internal.company.receive.wizard'
    _description = 'Receive Setsco Serials from Internal Company'

    note = fields.Text(string='Note')
    setsco_category_id = fields.Many2one('setsco.category', string='Serial Category')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', domain="[('company_id', '=', company_id)]", required=True)

    def _get_active_serials(self):
        active_ids = self.env.context.get('active_ids') or []
        return self.env['setsco.serial.number'].browse(active_ids)

    def action_confirm(self):
        serials = self._get_active_serials()
        if not serials:
            raise UserError(_('No serials selected.'))

        # Allow only serials that have been assigned to internal company and are in manufacturing
        invalid = serials.filtered(lambda s: not s.tranfered_to_internal_company or s.state not in ('manufacturing',) or s.internal_company_id.id == self.env.company.id)
        if invalid:
            raise ValidationError(_(
                'Only serials assigned to an internal company and in Manufacturing can be received.'
            ))

        # Save previous state before making changes for reverse functionality
        for serial in serials:
            # Save current state as previous state
            serial.write({
                'previous_state': serial.state,
                'previous_internal_company_id': serial.internal_company_id.id,
                'previous_location_id': serial.location_id.id,
                'previous_product_id': serial.product_id.id,
            })
            
            # If this is the first receive operation, also save as original state
            if not serial.original_state:
                serial.write({
                    'original_state': serial.state,
                    'original_internal_company_id': serial.internal_company_id.id,
                    'original_location_id': serial.location_id.id,
                    'original_product_id': serial.product_id.id,
                })

        serials.write({
            'state': 'warehouse',
            'internal_company_id': self.env.company.id,
            'tranfered_to_internal_company': False,
            
            'location_id': self.warehouse_id.lot_stock_id.id,
            'product_id': self.product_id.id,
        })

        for serial in serials:
            serial.message_post(body=_('Received back from internal company: %s') % (serial.internal_company_id.name or ''))

        return

    def action_reverse_receive(self):
        """Reverse the receive operation for selected serials"""
        self.ensure_one()
        serials = self._get_active_serials()
        if not serials:
            raise UserError(_('No serials selected.'))

        # Filter serials that can be reversed
        reversible_serials = serials.filtered(lambda s: s.can_reverse)
        if not reversible_serials:
            raise UserError(_('No serials can be reversed. Only serials with previous state can be reversed.'))

        # Reverse each serial
        reversed_count = 0
        for serial in reversible_serials:
            try:
                serial.action_reverse_transfer()
                reversed_count += 1
            except Exception as e:
                _logger.error(f'Failed to reverse serial {serial.name}: {str(e)}')

        if reversed_count == 1:
            message = _('1 serial has been successfully reversed.')
        else:
            message = _('%d serials have been successfully reversed.') % reversed_count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }


