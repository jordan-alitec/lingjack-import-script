# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ChangeBomComponentWizard(models.TransientModel):
    _name = 'change.bom.component.wizard'
    _description = 'Change BoM Component Wizard'

    current_product_id = fields.Many2one(
        'product.product',
        string='Current Component',
        required=True,
        readonly=True,
        help='The component product that will be replaced'
    )

    new_product_id = fields.Many2one(
        'product.product',
        string='New Component',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
        help='Select the new component product to replace the current one'
    )

    bom_line_ids = fields.Many2many(
        'mrp.bom.line',
        string='Affected BoM Lines',
        readonly=True,
        help='BoM lines that will be updated with the new component'
    )

    bom_count = fields.Integer(
        string='Number of BoMs',
        compute='_compute_bom_count',
        readonly=True
    )

    line_count = fields.Integer(
        string='Number of Lines',
        compute='_compute_line_count',
        readonly=True
    )

    @api.depends('bom_line_ids')
    def _compute_bom_count(self):
        for record in self:
            record.bom_count = len(record.bom_line_ids.mapped('bom_id'))

    @api.depends('bom_line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.bom_line_ids)

    @api.model
    def default_get(self, fields_list):
        """Set default values based on context"""
        res = super().default_get(fields_list)

        # Get product from context (handle both product.product and product.template)
        current_product_id = None
        product_template_id = self.env.context.get('active_product_tmp_id')
        product_product_id = self.env.context.get('active_product_id') or self.env.context.get('current_product_id')

        if product_product_id:
            # Direct product.product ID
            current_product_id = product_product_id
            current_product = self.env['product.product'].browse(current_product_id)
        elif product_template_id:
            # Need to find product.product from product.template
            product_template = self.env['product.template'].browse(product_template_id)
            # Get the first product variant
            products = product_template.product_variant_ids
            if products:
                current_product = products[0]
                current_product_id = current_product.id

        if current_product_id:
            res['current_product_id'] = current_product_id

            # If we have specific BoM context, only show lines from those BoMs
            if self.env.context.get('active_model') == 'mrp.bom':
                if self.env.context.get('active_ids'):
                    # Multiple BoMs selected - find lines from these BoMs that use the product
                    bom_lines = self.env['mrp.bom.line'].search([
                        ('bom_id', 'in', self.env.context.get('active_ids')),
                        ('product_id', '=', current_product_id)
                    ])
                    res['bom_line_ids'] = [(6, 0, bom_lines.ids)]
                elif self.env.context.get('active_id'):
                    # Single BoM
                    bom_lines = self.env['mrp.bom.line'].search([
                        ('bom_id', '=', self.env.context.get('active_id')),
                        ('product_id', '=', current_product_id)
                    ])
                    res['bom_line_ids'] = [(6, 0, bom_lines.ids)]
            else:
                # Find all BoM lines that use this product as component
                bom_lines = self.env['mrp.bom.line'].search([
                    ('product_id', '=', current_product_id)
                ])
                res['bom_line_ids'] = [(6, 0, bom_lines.ids)]

        return res

    @api.onchange('new_product_id')
    def _onchange_new_product_id(self):
        """Validate the new product selection"""
        if self.new_product_id and self.current_product_id:
            if self.new_product_id.id == self.current_product_id.id:
                raise UserError(_('The new component must be different from the current component.'))

            # Check if the new product is already used in any of the affected BoMs
            affected_boms = self.bom_line_ids.mapped('bom_id')
            for bom in affected_boms:
                existing_lines = bom.bom_line_ids.filtered(
                    lambda line: line.product_id.id == self.new_product_id.id
                )
                if existing_lines:
                    raise UserError(_(
                        'Product "%s" is already used as a component in BoM "%s". '
                        'Please select a different product.'
                    ) % (self.new_product_id.name, bom.display_name))

    def action_change_component(self):
        """Change the component in all affected BoM lines"""
        self.ensure_one()

        if not self.new_product_id:
            raise UserError(_('Please select a new component product.'))

        if self.new_product_id.id == self.current_product_id.id:
            raise UserError(_('The new component must be different from the current component.'))

        # Update all BoM lines
        updated_count = 0
        for bom_line in self.bom_line_ids:
            try:
                bom_line.write({
                    'product_id': self.new_product_id.id,
                })
                updated_count += 1
                _logger.info(
                    f"Updated BoM line {bom_line.id} from {self.current_product_id.name} to {self.new_product_id.name}")
            except Exception as e:
                _logger.error(f"Error updating BoM line {bom_line.id}: {e}")
                raise UserError(_('Error updating BoM line: %s') % str(e))

        # Show success message
        message = _(
            'Successfully updated %d BoM line(s) from "%s" to "%s".'
        ) % (updated_count, self.current_product_id.name, self.new_product_id.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Component Changed'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }