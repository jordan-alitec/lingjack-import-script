# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class MrpBomDuplicateWizard(models.TransientModel):
    _name = 'mrp.bom.duplicate.wizard'
    _description = 'Duplicate BoM Wizard'

    source_bom_id = fields.Many2one('mrp.bom', string='Source BoM', required=True, readonly=True)
    source_product_id = fields.Many2one('product.product', string='Source Product', readonly=True)
    source_product_tmpl_id = fields.Many2one('product.template', string='Source Product Template', readonly=True)

    target_product_id = fields.Many2one('product.product', string='Target Product', domain="[('type', '=', 'consu'),('route','=','make')]", required=False)
    target_product_tmpl_id = fields.Many2one('product.template', string='Target Product Template', required=False)

    copy_reference = fields.Char(string='New Reference')
    copy_code_suffix = fields.Char(string='Reference Suffix', help='Optional suffix to append to BoM reference during copy')

    @api.onchange('target_product_id')
    def _onchange_target_product_id(self):
        if self.target_product_id:
            self.target_product_tmpl_id = self.target_product_id.product_tmpl_id

    @api.onchange('target_product_tmpl_id')
    def _onchange_target_product_tmpl_id(self):
        if self.target_product_tmpl_id and (not self.target_product_id or self.target_product_id.product_tmpl_id != self.target_product_tmpl_id):
            # Clear product variant if template changed to avoid mismatch
            self.target_product_id = False

    def _ensure_unique_manufacturing_bom(self, product_id, product_tmpl_id):
        Bom = self.env['mrp.bom']
        domain = [('type', '=', 'normal'), ('active', '=', True)]
        if product_id:
            domain.append(('product_id', '=', product_id))
        else:
            domain += [('product_tmpl_id', '=', product_tmpl_id), ('product_id', '=', False)]
        if Bom.search_count(domain):
            raise ValidationError(_('An active manufacturing BoM already exists for the selected product.'))

    def action_confirm(self):
        self.ensure_one()
        if not (self.target_product_id or self.target_product_tmpl_id):
            raise UserError(_('Please select a target Product or Product Template.'))

        # Validate uniqueness
        self._ensure_unique_manufacturing_bom(self.target_product_id.id if self.target_product_id else False,
                                              self.target_product_tmpl_id.id if self.target_product_tmpl_id else False)

        # Prepare context for copy function
        copy_context = {}
        
        if self.target_product_id:
            copy_context.update({
                'duplicate_target_product_id': self.target_product_id.id,
            })
        else:
            copy_context.update({
                'duplicate_target_product_tmpl_id': self.target_product_tmpl_id.id,
            })
        
        # Add reference information to context
        if self.copy_reference:
            copy_context['duplicate_new_reference'] = self.copy_reference
        elif self.copy_code_suffix and self.source_bom_id.code:
            copy_context['duplicate_reference_suffix'] = self.copy_code_suffix

        # Call copy with context
        new_bom = self.source_bom_id.with_context(copy_context).copy()

        action = self.env.ref('mrp.mrp_bom_form_action').read()[0]
        action.update({
            'views': [(self.env.ref('mrp.mrp_bom_form_view').id, 'form')],
            'res_id': new_bom.id,
            'target': 'current',
        })
        return action


