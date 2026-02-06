# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MrpPurchaseRequestWizard(models.TransientModel):
    _name = 'mrp.purchase.request.wizard'
    _description = 'Purchase Request Wizard for Manufacturing Order'

    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        required=True,
        readonly=True
    )
    
    action_type = fields.Selection([
        ('create_new', 'Create New Purchase Request'),
        ('append_existing', 'Append to Existing Purchase Request')
    ], string='Action', required=True, default='create_new')
    
    existing_pr_id = fields.Many2one(
        'purchase.requisition',
        string='Existing Purchase Request',
        domain="[('state', '=', 'draft'),('purchase_type_id.name','=','Production')]",
        help='Select an existing draft purchase request to append components to'
    )
    
    component_line_ids = fields.One2many(
        'mrp.purchase.request.wizard.line',
        'wizard_id',
        string='Components',
        readonly=False
    )
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get existing draft purchase requests
        existing_prs = self.env['purchase.requisition'].search([
            ('state', '=', 'draft')
        ])
        
        if existing_prs:
            res['action_type'] = 'append_existing'
            res['existing_pr_id'] = existing_prs[0].id
        
        # Debug: Check context for component lines
        if 'default_component_line_ids' in self.env.context:
            # Include component lines from context
            if 'component_line_ids' in fields_list:
                res['component_line_ids'] = self.env.context['default_component_line_ids']
        
        return res
    
    def action_create_purchase_request(self):
        """Create or append to purchase request"""
        self.ensure_one()
        
        # Force a flush to ensure all changes are saved
        self.env.flush_all()
        
        # Debug: Check what lines we have
      
        # Filter out lines without products (deleted lines)
        valid_lines = self.component_line_ids.filtered(lambda l: l.product_id)
       
        
        if not valid_lines:
            raise UserError(_('No components to add to purchase request.'))
        
        if self.action_type == 'create_new':
            return self._create_new_purchase_request(valid_lines)
        else:
            return self._append_to_existing_purchase_request(valid_lines)
    
    def _create_new_purchase_request(self, valid_lines):
        """Create a new purchase request"""
        # Create purchase requisition
        pr_vals = {
            'name': f'PR for {self.production_id.name}',
            'purchase_type_id': self.env['purchase.type'].sudo().search([('name', '=', 'Production')],limit=1).id,
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
            'state': 'draft',
        }
        
        pr = self.env['purchase.requisition'].create(pr_vals)
        
        # Add component lines
        for line in valid_lines:
            line_vals = {
                'requisition_id': pr.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': 0.0,  # Will be filled by user
            }
            self.env['purchase.requisition.line'].create(line_vals)
        
        # Post message to MO
        self.production_id.message_post(
            body=_('Purchase Request %s created for non-stock components.') % pr.name
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'purchase.requisition',
            'res_id': pr.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _append_to_existing_purchase_request(self, valid_lines):
        """Append components to existing purchase request"""
        if not self.existing_pr_id:
            raise UserError(_('Please select an existing purchase request.'))
        
        # Check for existing lines to avoid duplicates
        existing_products = self.existing_pr_id.line_ids.mapped('product_id')
        
        for line in valid_lines:
            if line.product_id in existing_products:
                # Update existing line quantity
                existing_line = self.existing_pr_id.line_ids.filtered(
                    lambda l: l.product_id == line.product_id
                )
                if existing_line:
                    existing_line.product_qty += line.product_qty
            else:
                # Create new line
                line_vals = {
                    'requisition_id': self.existing_pr_id.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,
                    'product_uom_id': line.product_uom_id.id,
                    'price_unit': 0.0,
                }
                self.env['purchase.requisition.line'].create(line_vals)
        
        # Post message to MO
        self.production_id.message_post(
            body=_('Components added to existing Purchase Request %s.') % self.existing_pr_id.name
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'purchase.requisition',
            'res_id': self.existing_pr_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MrpPurchaseRequestWizardLine(models.TransientModel):
    _name = 'mrp.purchase.request.wizard.line'
    _description = 'Purchase Request Wizard Line'

    wizard_id = fields.Many2one(
        'mrp.purchase.request.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=False,  # Allow empty for deleted lines
        readonly=False
    )
    
    product_qty = fields.Float(
        string='Quantity',
        required=False,  # Allow empty for deleted lines
        readonly=False
    )

        
    free_qty = fields.Float(
        string='Free to Use',
        related='product_id.free_qty',
        readonly=True
    )
    
    
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=False,  # Allow empty for deleted lines
        readonly=False,
        domain="[('category_id', '=', product_uom_category_id)]",
        ondelete="restrict",
    )
    product_uom_category_id = fields.Many2one(
        comodel_name='uom.category',
        related='product_id.uom_id.category_id',
    )
    
    move_raw_id = fields.Many2one(
        'stock.move',
        string='Raw Material Move',
        readonly=False,

    )
