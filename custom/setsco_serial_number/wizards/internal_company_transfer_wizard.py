# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class SetscoInternalCompanyTransferWizard(models.TransientModel):
    """Wizard to assign SETSCO/TUV serials to an internal company.

    This sets the serials into manufacturing state for the external branch
    and records the internal company and assignment date.
    """
    _name = 'setsco.internal.company.transfer.wizard'
    _description = 'Assign Setsco Serials to Internal Company'

    internal_company_id = fields.Many2one(
        'res.company', string='Internal Company', required=True,
        help='Internal company to which these serials are assigned'
    )

    note = fields.Text(string='Note')

    def _get_active_serials(self):
        active_ids = self.env.context.get('active_ids') or []
        return self.env['setsco.serial.number'].browse(active_ids)

    def action_confirm(self):
        self.ensure_one()
        serials = self._get_active_serials()
        if not serials:
            raise UserError(_('No serials selected.'))

        # Basic validation: only allow in new/warehouse to move to manufacturing for internal company
        invalid = serials.filtered(lambda s: s.state not in ('new', 'warehouse'))
        if invalid:
            raise ValidationError(_(
                'Only serials in On hand or Finished Goods can be assigned to an internal company.'
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
            
            # If this is the first transfer operation, also save as original state
            if not serial.original_state:
                serial.write({
                    'original_state': serial.state,
                    'original_internal_company_id': serial.internal_company_id.id,
                    'original_location_id': serial.location_id.id,
                    'original_product_id': serial.product_id.id,
                })

        serials.write({
            'state': 'manufacturing',
            'internal_company_id': self.internal_company_id.id,
            'tranfered_to_internal_company': True,
        })

        for serial in serials:
            serial.message_post(body=_('Assigned to internal company: %s') % self.internal_company_id.name)

        return True

    def action_reverse_transfer(self):
        """Reverse the transfer operation for selected serials"""
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


