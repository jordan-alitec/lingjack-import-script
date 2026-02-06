from odoo import models, fields,api,_
from odoo.exceptions import UserError
from odoo.tools import format_datetime
from odoo.osv import expression
from dateutil.relativedelta import relativedelta


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_restricted_item = fields.Boolean(string="Restricted Item")
    is_share_product = fields.Boolean(string="Share Product")

    product_currency_id = fields.Many2one('res.currency', string='Currency')
    currency_rate = fields.Float(string="Currency Rate", digits=(12, 4))
    projected_cost  = fields.Char(string="Projected Cost")
    project_cost_home = fields.Float(string="Project Cost (Home)", compute="_compute_project_cost_home", store=True)
    #temp field for import
    website_url = fields.Char(string="Website URL", )

    ref_doc = fields.Char(string="Ref Doc")
    brand_id = fields.Many2one('product.brand', string="Brand")
    product_model_id = fields.Many2one('product.model', string="Model")
    version_id = fields.Many2one('product.version', string="Rev No")

    is_master_bom = fields.Boolean(string="Master BOM")
    is_export_control = fields.Boolean(string="Export Control Item")

    min_selling_price = fields.Monetary(string='Min. Selling Price', currency_field='currency_id')
    product_description = fields.Text(string="Product Description")
    production_remarks = fields.Text(string="Production Remarks")
    special_remarks = fields.Text(string="Special Remarks")
    dwg_no = fields.Char(string="Dwg No")
    internal_purchase_remarks = fields.Html()
    sales_supplier_warranty = fields.Float(string="Sales Warranty Period",digits=(10, 0))


    @api.depends('projected_cost', 'currency_rate')
    def _compute_project_cost_home(self):
        for record in self:
            try:
                projected = float(record.projected_cost)
            except (ValueError, TypeError):
                projected = 0.0
            record.project_cost_home = projected * record.currency_rate

    @api.onchange('product_tag_ids')
    def _onchange_product_tags(self):
        for rec in self:
            if rec.product_tag_ids:
                sorted_tags = sorted(
                    rec.product_tag_ids,
                    key=lambda t: t.tag_category_id.sequence if t.tag_category_id else 0
                )
                rec.product_tag_ids = [(6, 0, [tag.id for tag in sorted_tags])]

                rec.product_description = ', '.join(tag.name for tag in sorted_tags)

    def write(self, vals):
        # If standard_price is being updated, skip restriction check
        if 'standard_price' not in vals:
            user_has_access = self.env.user.has_group('lingjack_operation.group_control_restricted_item')
            restricted_records = self.filtered('is_restricted_item')
            if restricted_records and not user_has_access:
                raise UserError(_("You are not allowed to edit this item."))
        
        return super(ProductTemplate, self).write(vals)
    
    def unlink(self):       
        user_has_access = self.env.user.has_group('lingjack_operation.group_control_restricted_item')
        
        for record in self:
            is_restricted = record.is_restricted_item
            if is_restricted and not user_has_access:
                raise UserError(_("You are not allowed to delete this item."))
        
        return super(ProductTemplate, self).unlink()

    def action_open_edit_hs_origin_weight(self):
        """Open the Edit Product Template wizard prefilled with this template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Shipping Info',
            'res_model': 'lingjack.edit.product.template.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_tmpl_id': self.id},
        }

    # Deprecated method
    # def create(self, vals):
    #     res = super(ProductTemplate, self).create(vals)
    #     user_has_access = self.env.user.has_group('lingjack_operation.group_control_restricted_item')
    #     is_restricted = vals.get('is_restricted_item', False)
    #     if not (user_has_access and is_restricted):
    #         raise UserError(
    #             _("You are not allowed to create this item."))
    #     return res


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'Brand of Product'

    name = fields.Char(string='Product', required=True)

class ProductModel(models.Model):
    _name = 'product.model'
    _description = 'Model of Product'

    name = fields.Char(string='Model', required=True)

class ProductVersion(models.Model):
    _name = 'product.version'
    _description = 'Version of Product'

    name = fields.Char(string='Version', required=True)



class ProductTag(models.Model):
    _inherit = 'product.tag'

    tag_category_id = fields.Many2one(
        'tag.category',
        string='Tag Category'
    )
    tag_category_sequence = fields.Integer(string='Sequence',compute='_compute_tag_category_sequence',store=False)

    @api.depends('tag_category_id.sequence')
    def _compute_tag_category_sequence(self):
        for tag in self:
            tag.tag_category_sequence = tag.tag_category_id.sequence if tag.tag_category_id else 0


class TagCategory(models.Model):
    _name = 'tag.category'
    _description = 'Category of  Tag'
    _order = 'sequence, name'


    name = fields.Char(string='Category of Tag', required=True)
    sequence = fields.Integer(string='Sequence')

    _sql_constraints = [
        ('unique_sequence', 'UNIQUE(sequence)', 'Sequence number must be unique.')
    ]


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    cost_price = fields.Monetary(string="Cost", currency_field="currency_id", help="Internal Cost for reference" )
    end_user_price = fields.Monetary(string="End User Price", currency_field="currency_id", help="Special end user price" )
    remarks = fields.Text(string="Remarks", help="Additional notes for this price rule" )


class ProductVariant(models.Model):
    _inherit = 'product.product'
    # Relate to template's field so product follows template restriction flag
    is_restricted_item = fields.Boolean(
        related='product_tmpl_id.is_restricted_item',
        string="Restricted Item",
    )

    def write(self, vals):
        # If standard_price is being updated, skip restriction check
        if 'standard_price' not in vals and 'fsm_quantity' not in vals:
            user_has_access = self.env.user.has_group('lingjack_operation.group_control_restricted_item')
            restricted_records = self.filtered('is_restricted_item')
            if restricted_records and not user_has_access:
                raise UserError(_("You are not allowed to edit this item."))
        
        return super(ProductVariant, self).write(vals)

    def unlink(self):
        user_has_access = self.env.user.has_group('lingjack_operation.group_control_restricted_item')
        for product in self:
            if product.is_restricted_item and not user_has_access:
                raise UserError(_("You are not allowed to delete this item."))
        return super(ProductVariant, self).unlink()

    def action_open_edit_hs_origin_weight(self):
        """Open the Edit Product wizard prefilled with this product variant."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Shipping Info',
            'res_model': 'lingjack.edit.product.template.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_id': self.id},
        }


    def open_at_forecasted(self):
        tree_view_id = self.env.ref('stock.view_stock_product_tree').id
        form_view_id = self.env.ref('stock.product_form_view_procurement_button').id
        domain = [('is_storable', '=', True)]
        product_id = self.env.context.get('product_id', False)
        product_tmpl_id = self.env.context.get('product_tmpl_id', False)

        if product_id:
            domain = expression.AND([domain, [('id', '=', product_id)]])
        elif product_tmpl_id:
            domain = expression.AND([domain, [('product_tmpl_id', '=', product_tmpl_id)]])


        to_date = fields.Datetime.now() + relativedelta(months=4)

        action = {
            'type': 'ir.actions.act_window',
            'views': [(tree_view_id, 'list'), (form_view_id, 'form')],
            'view_mode': 'list,form',
            'name': _('Products'),
            'res_model': 'product.product',
            'domain': domain,
            'context': dict(self.env.context, to_date=to_date),
            'display_name': format_datetime(self.env, to_date)
        }
        return action

