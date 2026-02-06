import ast

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)
class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    setsco_serial_ids = fields.One2many('setsco.serial.number', 'production_id',
                                        string='Setsco Serial Numbers')
    setsco_serial_count = fields.Integer(string='setsco Serial Count', compute='_compute_setsco_serial_count')
    requires_setsco_serials = fields.Boolean(string='Requires Setsco Serial Numbers',
                                             compute='_compute_requires_setsco_serials',
                                             store=True,
                                             help='Whether this production requires setsco serial numbers based on product configuration')
    can_assign_more_serials = fields.Boolean(string='Can Assign More Serials', 
                                              compute='_compute_can_assign_more_serials')
    to_remove_lst = fields.Char(string="to_remove")

    @api.depends('setsco_serial_ids')
    def _compute_setsco_serial_count(self):
        for production in self:
            production.setsco_serial_count = len(production.setsco_serial_ids)

    @api.depends('product_id.requires_setsco_serial')
    def _compute_requires_setsco_serials(self):
        for production in self:
            production.requires_setsco_serials = production.product_id.requires_setsco_serial

    @api.depends('setsco_serial_count', 'product_qty', 'requires_setsco_serials')
    def _compute_can_assign_more_serials(self):
        for production in self:
            production.can_assign_more_serials = (
                production.requires_setsco_serials and
                production.setsco_serial_count < production.product_qty
            )

    # @api.constrains('product_qty', 'setsco_serial_count', 'requires_setsco_serials')
    # def _check_setsco_serial_quantity(self):
    #     for production in self:
    #         if (production.requires_setsco_serials and
    #             production.state in ['confirmed', 'progress', 'to_close'] and
    #             production.product_qty > production.setsco_serial_count):
    #             raise ValidationError(
    #                 _('Cannot produce %s units of %s. Only %s setsco serial numbers are assigned. '
    #                   'Please assign more setsco serial numbers or reduce the quantity to produce.') %
    #                 (production.product_qty, production.product_id.name, production.setsco_serial_count)
    #             )

    def action_assign_setsco_serials(self):
        """Open wizard to assign setsco serial numbers to production"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Setsco Serial Numbers'),
            'res_model': 'setsco.serial.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_product_id': self.product_id.id,
                'default_quantity': self.product_qty,
            }
        }

    def action_view_setsco_serials(self):
        """View setsco serial numbers for this production"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Production Setsco Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
            'context': {
                'default_production_id': self.id,
                'default_product_id': self.product_id.id,
                'default_state': 'manufacturing'
            }
        }

    def pre_button_mark_done(self):
        """Pre-validation before marking production as done"""
        # Validate setsco serial count before marking done
        for production in self:
            if production.requires_setsco_serials:
                if production.setsco_serial_count < production.qty_producing:
                    raise ValidationError(
                        _('Cannot mark production order %s as done. '
                          'Product %s requires setsco serial numbers, but only %s serials are assigned '
                          'while %s units are being produced. '
                          'Please assign exactly %s setsco serial numbers before marking as done.') %
                        (production.name, production.product_id.name, 
                         production.setsco_serial_count, production.qty_producing, production.qty_producing)
                    )
        
        return super().pre_button_mark_done()

    def button_mark_done(self):
        """Override to update setsco serial numbers state and link to lot"""
        result = super().button_mark_done()
        self._reassign_setsco_serial_numbers()
        self._assign_setsco_number()
        return result

    def assign(self):
        self._assign_setsco_number()

    def _assign_setsco_number(self):
        for rec in self:
            if rec.product_id.requires_setsco_serial:
                picking = rec.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'] and p.mrp_production_id.id == rec.id)
  
                # Find all move lines from this production's pickings
                # Should not have more than one stock move
                move = self.env['stock.move'].search([
                    ('picking_id', 'in', picking.ids),
                    ('state', 'not in', ['done', 'cancel']),
                    ('product_id','=', rec.product_id.id),
                    ('product_id.requires_setsco_serial', '=', True)
                ],limit=1)
         
                # Just skip when there is no stock move skip here so that odoo will throw error when there is no setsco assigned
                if not move or not rec.setsco_serial_ids:
                    continue
                
                # Clear all quantity
                move.quantity = 0
                

                # Create new move lines, one per serial
                for serial in rec.setsco_serial_ids.filtered(lambda s: s.state == 'warehouse'):
                    ml_vals = {
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'quantity': 1,  # planned per-line quantity
                        'qty_done': 1,  # done per-line quantity
                        'picked': True,
                        'picking_id': move.picking_id.id,  # done per-line quantity
                        'lot_id': serial.lot_id.id if getattr(serial, 'lot_id', False) else False,
                        # Link serial by inverse One2many
                        'setsco_serial_ids': [(6, 0, [serial.id])],
                    }
                    self.env['stock.move.line'].sudo().create(ml_vals)
      
                
                
           

    def button_confirm(self):
        """Override to handle setsco serial requirements when production is confirmed"""
        result = super().button_confirm()
        
        # Note: Location updates for setsco serials now happen during assignment
        # in the setsco serial assignment wizard, not during confirmation
        
        return result


    def _reassign_setsco_serial_numbers(self):
        """Reassign remaining SETSCO serial numbers to the backorder MOs and process them."""
        mo_ids_to_backorder = self.env.context.get('mo_ids_to_backorder')

        for production in self:
            if not production.requires_setsco_serials:
                continue

            if mo_ids_to_backorder:
                # Skip if MO is not part of the backorder set (MO00003 in your case)
                if production.id not in mo_ids_to_backorder:
                    continue

                # Get all relevant serials from previous MOs
                previous_mos = production.backorder_ids

                #if exactly the same remove
                if len(previous_mos) == 1:
                    continue




                leftover_serials = self.env['setsco.serial.number'].search([
                    ('production_id', 'in', previous_mos.ids),
                    ('state', '=', 'manufacturing')
                ], order='id desc')

                backorder_id = previous_mos.filtered(lambda m: m.state not in ['done','cancel'])[0]
                previous_mo  = previous_mos.filtered(lambda m: m.state in ['done','cancel'])[0]

                # Assign lot it
                backorder_id.lot_producing_id = previous_mo.lot_producing_id.id


                # Only assign what is needed
                qty_needed = int(backorder_id.product_qty)

                serials_to_move = leftover_serials[:qty_needed]

                # Move serials to the backorder
                if serials_to_move:
                    serials_to_move.write({'production_id': backorder_id.id})

                    # # Process remaining serials (still in manufacturing, not used yet)
                    # for serial in remaining_serials:
                    #     serial.action_set_warehouse()
                    #
                    #     if production.lot_producing_id and not serial.lot_id:
                    #         serial.write({'lot_id': production.lot_producing_id.id})
                    #
                    #     if production.location_dest_id:
                    #         move = production.move_finished_ids.filtered(lambda m: m.product_id == serial.product_id)[
                    #                :1]
                    #         if move:
                    #             serial._update_location_from_stock_move(move)
                    #
                    # # Log message
                    # msg = _(
                    #     'Moved %d SETSCO serial number(s) to backorder %s: %s'
                    # ) % (
                    #           len(serials_to_move),
                    #           production.name,
                    #           ', '.join(serials_to_move.mapped('name'))
                    #       )
                    # production.message_post(body=msg)

            else:
                # No backorder logic — just process all serials
                if production.setsco_serial_ids.filtered(lambda s: s.state == 'warehouse'):
                    continue


                for serial in production.setsco_serial_ids.filtered(lambda s: s.state == 'manufacturing').sorted(key=lambda s: s.id)[:round(production.qty_producing)]:
                    serial.action_set_warehouse()

                    if production.lot_producing_id and not serial.lot_id:
                        serial.write({'lot_id': production.lot_producing_id.id})
                    
                    move = production.move_finished_ids.filtered(lambda m: m.product_id == serial.product_id)[:1]
                    if move:
                        _logger.info(f"\n\nUpdating location for serial {serial.name} from move {move.id}")
                        _logger.info(f"Move location: {move.state}")
                        serial._update_location_from_stock_move(move, button_done=True)

    def _update_setsco_serial_locations_from_moves(self):
        """Update setsco serial locations based on production moves"""
        for serial in self.setsco_serial_ids:
            if serial.state == 'manufacturing':
                # Update location based on current production move
                if self.move_raw_ids:
                    # Use the first raw material move as reference
                    raw_move = self.move_raw_ids[0]
                    serial._update_location_from_stock_move(raw_move)
                elif self.move_finished_ids:
                    # Use the finished goods move as reference
                    finished_move = self.move_finished_ids[0]
                    serial._update_location_from_stock_move(finished_move)

class StockLot(models.Model):
    _inherit = 'stock.lot'

    setsco_serial_ids = fields.One2many('setsco.serial.number', 'lot_id',
                                        string='Setsco Serial Numbers')
    setsco_serial_count = fields.Integer(string='Setsco Serial Count',
                                         compute='_compute_setsco_serial_count')

    @api.depends('setsco_serial_ids')
    def _compute_setsco_serial_count(self):
        for lot in self:
            lot.setsco_serial_count = len(lot.setsco_serial_ids)

    def action_view_setsco_serials(self):
        """View setsco serial numbers for this lot"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lot Setsco Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('lot_id', '=', self.id)],
            'context': {
                'default_lot_id': self.id,
                'default_product_id': self.product_id.id,
            }
        } 