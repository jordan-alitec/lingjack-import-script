from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_used_in_bom(self):
        """Override to add context for component change functionality"""
        self.ensure_one()

        # Get the original action from parent
        action = super().action_used_in_bom()

        # Add context to pass the current product ID
        if action and isinstance(action, dict):
            action['context'] = {
                'active_product_tmp_id': self.id,
                'change_component_mode': True,
            }

        return action


class ProductProduct(models.Model):
    _inherit = 'product.product'

    route = fields.Selection([
        ('buy', 'Buy'),
        ('make', 'Make'),
        ('buy_make', 'Buy / Make')
    ], string='Route', compute='_compute_route', store=True, help="Product route type based on procurement routes")

    def compute_route(self):
        for rec in self:
            rec._compute_route()


    @api.depends('route_ids', 'route_ids.is_manufacture')
    def _compute_route(self):
        """Compute route field based on product's procurement routes"""
        for rec in self:
            if not rec.route_ids:
                rec.route = False
                continue

            has_buy = False
            has_make = False

            for route in rec.route_ids:
                if 'buy' in route.name.lower():
                    has_buy = True
                if route.is_manufacture:
                    has_make = True

            if has_buy and has_make:
                rec.route = 'buy_make'
            elif has_buy:
                rec.route = 'buy'
            elif has_make:
                rec.route = 'make'
            else:
                rec.route = False

    def action_used_in_bom(self):
        """Override to add context for component change functionality"""
        self.ensure_one()

        # Get the original action from parent
        action = super().action_used_in_bom()

        # Add context to pass the current product ID
        if action and isinstance(action, dict):
            action['context'] = {
                'active_product_id': self.id,
                'change_component_mode': True,
            }

        return action