# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class MrpProductionSfpDistribution(models.Model):
    _name = 'mrp.production.sfp.distribution'
    _description = 'SFP Distribution Plan'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)

    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        required=True,
        ondelete='cascade'
    )

    procurement_group_id = fields.Many2one(
        'procurement.group',
        string='Procurement Group',
        related='production_id.procurement_group_id',
        store=True,
        readonly=True
    )

    distribution_type = fields.Selection([
        ('swo_line', 'SWO'),
        ('excess', 'Production'),
    ], string='Distribution Type', required=True, default='swo_line')

    sale_work_order_line_id = fields.Many2one(
        'sale.work.order.line',
        string='Sale Work Order Line',
        help='The SWO line that defines this distribution (only for swo_line type)'
    )

    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=True,
        domain="[('usage', '=', 'internal')]"
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )

    planned_qty = fields.Float(
        string='Planned Quantity',
        required=True,
        digits='Product Unit of Measure'
    )

    actual_qty = fields.Float(
        string='Actual Quantity',
        digits='Product Unit of Measure',
        readonly=True
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='SFP Transfer',
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', required=True)

    # Related fields for easier access
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        related='sale_work_order_line_id.sale_order_id',
        readonly=True,
        store=True
    )

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='sale_order_id.partner_id',
        readonly=True,
        store=True
    )

    @api.constrains('planned_qty')
    def _check_total_qty(self):
        return

    @api.constrains('distribution_type', 'sale_work_order_line_id')
    def _check_swo_line_required(self):
        """Ensure SWO line is provided for swo_line distribution type"""
        for record in self:
            if record.distribution_type == 'swo_line' and not record.sale_work_order_line_id:
                raise ValidationError(
                    _('Sale Work Order Line is required for SWO Line Specific distribution type')
                )

    def action_create_sfp_transfer(self, production_id = False):
        """Create SFP transfer for this distribution"""
        self.ensure_one()

        '''
              Do nothing when it is child mo, child mo we deal with preproduction only
        '''

        self.ensure_one()

        if production_id.location_src_id.id == production_id.location_dest_id.id or not production_id:
            return

        warehouse = self.production_id.picking_type_id.warehouse_id
        if not warehouse or not warehouse.sam_type_id:
            raise UserError(_('No Store Finished Product operation type configured'))

        # Create picking
        picking_vals = {
            'picking_type_id': warehouse.sam_type_id.id,
            'location_id': warehouse.sam_type_id.default_location_src_id.id,
            'location_dest_id': self.location_dest_id.id,
            'origin': f'{production_id.name} (SFP to {self.location_dest_id.name})',
            'mrp_production_id': production_id.id,
            'group_id': production_id.procurement_group_id.id if production_id.procurement_group_id else False,
            'state': 'draft',
        }

        picking = self.env['stock.picking'].create(picking_vals)

        # Create move - use qty_producing for transfer quantity
        transfer_qty = production_id.qty_producing if production_id.qty_producing > 0 else 0

        if transfer_qty <= 0:
            raise UserError(_('No quantity to transfer. Actual quantity must be greater than 0.'))

        move_vals = {
            'name': f"Store {self.product_id.display_name}",
            'product_id': self.product_id.id,
            'product_uom_qty': transfer_qty,
            'product_uom': self.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'origin': production_id.name,
            'group_id': production_id.procurement_group_id.id if production_id.procurement_group_id else False,
        }

       
        move = self.env['stock.move'].create(move_vals)
        _logger.warning(f"Move vals: {move.location_dest_id.display_name}")
        _logger.warning(f"Production id: {picking.location_dest_id.display_name}")

        # Update distribution
        self.write({
            'picking_id': picking.id,
            'state': 'ready'
        })

        # Confirm the picking
        picking.action_confirm()

        return {
            'type': 'ir.actions.act_window',
            'name': _('SFP Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _on_picking_done(self, picking):
        """Called when the SFP transfer is marked as done"""
        if self.distribution_type == 'swo_line' and self.sale_work_order_line_id:
            # Update the SWO line's qty_in_stock
            self.sale_work_order_line_id.qty_in_stock = self.actual_qty
            # Trigger state recomputation
            self.sale_work_order_line_id._compute_state()

            # Notify CS in charge
            self._notify_cs_in_charge()

    def _notify_cs_in_charge(self):
        """Notify CS in charge when SFP transfer is completed"""
        if not self.sale_work_order_line_id or not self.sale_work_order_line_id.cs_in_charge_id:
            return

        cs_user = self.sale_work_order_line_id.cs_in_charge_id
        swo_line = self.sale_work_order_line_id

        # Create notification message
        message = _(
            'SFP Transfer Completed: %(qty)s units of %(product)s have been stored in %(location)s for %(swo_line)s.'
        ) % {
                      'qty': self.actual_qty,
                      'product': self.product_id.display_name,
                      'location': self.location_dest_id.display_name,
                      'swo_line': swo_line.work_order_id.name
                  }

        # # Post message to the sale order
        # if swo_line.sale_order_id:
        #     swo_line.sale_order_id.message_post(
        #         body=message,
        #         message_type='notification',
        #         partner_ids=[cs_user.partner_id.id] if cs_user.partner_id else []
        #     )

        # Also post to the SWO line
        swo_line.work_order_id.message_post(
            body=message,
            message_type='notification',
            partner_ids=[cs_user.partner_id.id] if cs_user.partner_id else []
        )

    def action_view_transfer(self):
        """View the SFP transfer"""
        self.ensure_one()

        if not self.picking_id:
            raise UserError(_('No transfer created for this distribution'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('SFP Transfer'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
