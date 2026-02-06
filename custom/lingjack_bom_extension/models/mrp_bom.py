from odoo import models, fields, api,_
from odoo.exceptions import ValidationError,UserError

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    # worksheet template for the bom
    worksheet_type = fields.Selection([
        ('pdf', 'PDF'),
        ('google_slide', 'Google Slide'),
        ('text', 'Text')
    ], string="Worksheet", default="text")
    
    note = fields.Html('Description')
    worksheet = fields.Binary('PDF')
    worksheet_google_slide = fields.Char(
        'Google Slide',
        help="Paste the URL of your Google Slide. Make sure the access to the document is public.",
        tracking=True
    )

    # Lingjack Digital
    area_id = fields.Char(string="Area ID", help="Area identification code")
    sid_prefix = fields.Char(string="SID Prefix", help="System ID prefix")
    node_type_id = fields.Char(string="Node Type ID", help="Node type identification")


    @api.model
    def write(self, vals):
        """Propagate worksheet updates to operations."""
        res = super().write(vals)

        fields_to_sync = {'worksheet_type', 'note', 'worksheet', 'worksheet_google_slide'}
        if any(field in vals for field in fields_to_sync):
            for bom in self:
                for operation in bom.operation_ids:
                    operation_vals = {}
                    if 'worksheet_type' in vals:
                        operation_vals['worksheet_type'] = bom.worksheet_type
                    if 'note' in vals:
                        operation_vals['note'] = bom.note
                    if 'worksheet' in vals:
                        operation_vals['worksheet'] = bom.worksheet
                    if 'worksheet_google_slide' in vals:
                        operation_vals['worksheet_google_slide'] = bom.worksheet_google_slide
                    if operation_vals:
                        operation.write(operation_vals)
        return res

    @api.constrains('product_tmpl_id', 'product_id', 'type', 'active')
    def _check_unique_manufacturing_bom(self):
        """Ensure only one active manufacturing BoM exists per final product (not kit)"""
        for record in self:
            if record.active and record.type == 'normal':
                domain = [
                    ('type', '=', 'normal'),
                    ('active', '=', True),
                    ('id', '!=', record.id),
                ]

                if record.product_id:
                    domain.append(('product_id', '=', record.product_id.id))
                    existing_boms = self.search(domain)
                    if existing_boms:
                        raise ValidationError(_(
                            'Only one active manufacturing BoM is allowed per product. '
                            'Another manufacturing BoM already exists for product "%s".'
                        ) % record.product_id.name)
                else:
                    domain.extend([
                        ('product_tmpl_id', '=', record.product_tmpl_id.id),
                        ('product_id', '=', False),
                    ])
                    existing_boms = self.search(domain)
                    if existing_boms:
                        raise ValidationError(_(
                            'Only one active manufacturing BoM is allowed per product template. '
                            'Another manufacturing BoM already exists for product template "%s".'
                        ) % record.product_tmpl_id.name)


    def action_change_bom_component(self):
        """Open wizard to change a component in selected BoMs"""
        product_id = None
        product_template_id = self.env.context.get('active_product_tmp_id')
        product_product_id = self.env.context.get('active_product_id')

        if product_product_id:
            product_id = product_product_id
            product = self.env['product.product'].browse(product_id)
        elif product_template_id:
            product_template = self.env['product.template'].browse(product_template_id)
            products = product_template.product_variant_ids
            if not products:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No Product Variants'),
                        'message': _('Product template has no variants.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            product = products[0]
            product_id = product.id
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Product Selected'),
                    'message': _('Please select a product to change in BoMs.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        bom_lines = self.env['mrp.bom.line'].search([
            ('bom_id', 'in', self.ids),
            ('product_id', '=', product_id)
        ])
        if not bom_lines:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Product Not Found'),
                    'message': _('Product "%s" is not used as a component in the selected BoMs.') % product.name,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'name': _('Change BoM Component'),
            'type': 'ir.actions.act_window',
            'res_model': 'change.bom.component.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'mrp.bom',
                'active_ids': self.ids,
                'active_product_id': product_id,
                'current_product_id': product_id,
            }
        }
        

    def copy(self, default=None):
        """Override copy to show wizard for product selection"""
        # Check if we have a target product in context (from wizard confirmation)
        if self.env.context.get('duplicate_target_product_id') or self.env.context.get('duplicate_target_product_tmpl_id'):
            # Proceed with normal copy using context values
            copy_default = default or {}

            # Set target product from context
            if self.env.context.get('duplicate_target_product_id'):
                copy_default.update({
                    'product_id': self.env.context['duplicate_target_product_id'],
                    'product_tmpl_id': self.env['product.product'].browse(self.env.context['duplicate_target_product_id']).product_tmpl_id.id,
                })
            elif self.env.context.get('duplicate_target_product_tmpl_id'):
                copy_default.update({
                    'product_id': False,
                    'product_tmpl_id': self.env.context['duplicate_target_product_tmpl_id'],
                })

            # Set custom reference if provided
            if self.env.context.get('duplicate_new_reference'):
                copy_default['code'] = self.env.context['duplicate_new_reference']
            elif self.env.context.get('duplicate_reference_suffix') and self.code:
                copy_default['code'] = f"{self.code}{self.env.context['duplicate_reference_suffix']}"

            return super().copy(copy_default)

        # No target product in context, raise an error to prevent default duplication
        self.action_duplicate_bom_wizard()
        raise UserError(_('Please use the Duplicate wizard to select a target product for the new BoM.'))

    def action_duplicate_bom_wizard(self):
        """Open wizard to duplicate BoM and choose the target product"""
        self.ensure_one()
        return {
            'name': _('Duplicate BoM'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom.duplicate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'mrp.bom',
                'active_id': self.id,
                'default_source_bom_id': self.id,
                'default_source_product_id': False,
                'default_source_product_tmpl_id': self.product_tmpl_id.id if self.product_tmpl_id else False,
            }
        }

    def action_duplicate(self):
        """Server action to duplicate BoM with wizard"""
        return self.action_duplicate_bom_wizard()
class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'
    com_no = fields.Char(string='Component No', related="product_id.default_code")
    # stock_item = fields.Char(string='Stock Item', related="product_id.stock_item")
    route = fields.Selection(related="product_id.route")

    # operation_template_id removed from here
    on_hand_qty = fields.Float(string='On Hand Qty', compute='_compute_on_hand_qty' )
    forecast_qty = fields.Float(string='Forecast Qty', compute='_compute_forecast_qty')




    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for rec in self:
            rec.on_hand_qty = rec.product_id.qty_available if rec.product_id else 0

    @api.depends('product_id')
    def _compute_forecast_qty(self):
        for rec in self:
            rec.forecast_qty = rec.product_id.virtual_available if rec.product_id else 0


