from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    stock_item = fields.Boolean(
        string='Stock Item',
        help='Indicates if this product is a stock item (checked = Stock, unchecked = Non-Stock).'
    )
    take_in_pale = fields.Boolean(
        string='Take Item in Bulk?',
        help='Indicates the component that will take in pale will create weekly in the internal transfer note'
    )

    fire_rating = fields.Char(
        string='Fire Rating',
        help='Fire rating classification (e.g., Class A, Class B, Class C)'
    )

    capacity = fields.Char(
        string='Capacity',
        help='Capacity of the fire extinguisher (e.g., 9kg, 6L, 2kg)'
    )
    #temp field
    is_setsco_label = fields.Boolean(
        string='Is Setsco Label',
        default=False,
        readonly=False,
        help='Check this box if products in this category should be excluded from two-step manufacturing pick component transfer notes'
    )

    manual_lot_reservation = fields.Boolean(
        string='Manual Lot Reservation Required',
        default=False,
        help='If checked,production operator must manually select lot number before proceeding. If unchecked, system will auto-select lot.'
    )



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

    def action_create_component_transfer(self):
        """Create a component transfer picking for selected products and set to To Do.
        - Uses company-configured component transfer picking type.
        - Creates one picking with one move per selected product, quantity = 1 by default.
        """
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        company = self.env.company

        if not company.component_transfer_picking_type_id:
            raise UserError(_('Please configure Component Transfer Operation Type in Settings.'))

        picking_type = company.component_transfer_picking_type_id

        if not picking_type.default_location_src_id or not picking_type.default_location_dest_id:
            raise UserError(_('The selected Operation Type must have default source and destination locations.'))

        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'origin': _('Product Component Transfer'),
            'company_id': company.id,
        }
        picking = Picking.create(picking_vals)

        for product in self:
            # create one move per product with qty 1; users can adjust later
            Move.create({
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': 0,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'company_id': company.id,
            })

        # confirm the picking so it becomes waiting/ready (To Do)
        picking.action_confirm()

     
        # _logger.warning("\n\n\naction_create_component_transfer")
        # _logger.warning(action)
            
        return {
                "type": "ir.actions.act_window",
                "res_model": "stock.picking",
                "view_mode": "form",
                "views": [(self.env.ref("stock.view_picking_form").id, "form")],
                "res_id": picking.id,
                "target": "current",
            }