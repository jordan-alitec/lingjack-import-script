from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    setsco_serial_id = fields.Many2one(
        'setsco.serial.number',
        string='Setsco Serial Number',
        domain="[('state', 'in', ['new', 'warehouse']), ('product_id', '=', product_id)]",
        help='Setsco serial number assigned to this manufacturing order'
    )

    @api.constrains('setsco_serial_id', 'product_id')
    def _check_setsco_serial_product_match(self):
        for record in self:
            if record.setsco_serial_id and record.product_id:
                # Check if the product matches
                if record.setsco_serial_id.product_id != record.product_id:
                    raise ValidationError(_(
                        'The selected Setsco serial number is not compatible with the product %s. '
                        'Please select a serial number assigned to this product.'
                    ) % record.product_id.name)

                # Check if the serial number is linked to another serial number
                if record.setsco_serial_id.parent_serial_id:
                    # Get all linked serial numbers (parent and siblings)
                    linked_serials = record.setsco_serial_id.parent_serial_id.child_serial_ids
                    linked_products = linked_serials.mapped('product_id')
                    
                    # Check if the finished product is in the linked products
                    if record.product_id not in linked_products:
                        raise ValidationError(_(
                            'The finished product %s must be one of the products linked to the '
                            'parent Setsco serial number %s.'
                        ) % (record.product_id.name, record.setsco_serial_id.parent_serial_id.name))

    @api.onchange('product_id')
    def _onchange_product_id_setsco(self):
        """Clear setsco_serial_id when product changes"""
        if self.product_id:
            self.setsco_serial_id = False

    # def _post_inventory(self, cancel_backorder=False):
    #     """Update setsco serial number state after inventory posting"""
    #     res = super()._post_inventory(cancel_backorder=cancel_backorder)
    #     for record in self:
    #         if record.setsco_serial_id and record.state == 'done':
    #             record.setsco_serial_id.action_set_warehouse()
    #     return res

    def action_confirm(self):
        """Update setsco serial number state when MO is confirmed"""
        res = super().action_confirm()
        for record in self:
            if record.setsco_serial_id:
                record.setsco_serial_id.action_set_manufacturing()
        return res 

    