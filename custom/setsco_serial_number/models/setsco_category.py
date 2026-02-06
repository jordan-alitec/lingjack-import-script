# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SetscoCategory(models.Model):
    _name = 'setsco.category'
    _description = 'Setsco Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help='Name of the Setsco category'
    )

    # Optional description field for additional context
    description = fields.Text(
        string='Description',
        tracking=True,
        help='Optional description of the Setsco category'
    )

    # Active field for archiving categories
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Uncheck to archive this category'
    )

    safety_stock_level = fields.Float(string="Safety Stock Level",tracking=True,digits='Product Unit of Measure')

    # Computed fields for smart button
    available_serials_count = fields.Integer(
        string='Available Serials Count',
        compute='_compute_available_serials_count',
        help='Number of setsco serial numbers in "new" state for this category'
    )

    def _compute_available_serials_count(self):
        """Compute the count of available serials (new state) for this category"""
        for record in self:
            record.available_serials_count = self.env['setsco.serial.number'].search_count([
                ('setsco_category_id', '=', record.id),
                ('state', '=', 'new')
            ])

    def action_view_available_serials(self):
        """Smart button action to view available serials for this category"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Available Setsco Serial Numbers - %s') % self.name,
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [
                ('setsco_category_id', '=', self.id),
            ],
            'context': {
                'default_setsco_category_id': self.id,
                'default_state': 'new',
                'search_default_available_by_category': 1
            },
            'help': _('Shows setsco serial numbers in "new" state for category %s') % self.name
        }

    def name_get(self):
        """Return name for display purposes"""
        result = []
        for record in self:
            result.append((record.id, record.name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced name search for better usability"""
        if args is None:
            args = []
        domain = args[:]
        if name:
            domain += [('name', operator, name)]
        records = self.search(domain, limit=limit)
        return records.name_get() 