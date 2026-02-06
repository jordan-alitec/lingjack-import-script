# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductionSerial(models.Model):
    _inherit = 'production.serial'

    setsco_serial_id = fields.Many2one(
        'setsco.serial.number',
        string='Setsco Serial Number',
        ondelete='set null',
        copy=False,
    )

    @api.constrains('setsco_serial_id', 'state')
    def _check_setsco_serial_unique(self):
        """One Setsco can only be linked to one active production.serial."""
        for rec in self:
            if not rec.setsco_serial_id or rec.state != 'active':
                continue
            other = self.search([
                ('setsco_serial_id', '=', rec.setsco_serial_id.id),
                ('state', '=', 'active'),
                ('id', '!=', rec.id),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    'Setsco Serial Number "%s" is already linked to another active Production Serial (%s).',
                    rec.setsco_serial_id.name,
                    other.name,
                ))
