from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _create_return(self):
        """Override to automatically assign setsco serials for returns"""
        # Call parent method to create the return picking
        new_picking = super()._create_return()
        
        # Store the original delivery picking ID in the context for later use
        new_picking.env.context = dict(new_picking.env.context, 
                                      setsco_original_picking_id=self.picking_id.id)
        
        return new_picking


class ReturnPickingLine(models.TransientModel):
    _inherit = 'stock.return.picking.line'

    def _prepare_move_default_values(self, new_picking):
        """Override to ensure proper move preparation for setsco serials"""
        vals = super()._prepare_move_default_values(new_picking)
        
        # Add any specific handling for setsco serial products if needed
        if self.product_id.requires_setsco_serial:
            # Ensure the move is properly set up for setsco serial handling
            pass
            
        return vals


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_confirm(self):
        """Override to handle setsco serial assignment for returns after confirmation"""
        result = super().action_confirm()
        
        # For return pickings, assign setsco serials after confirmation
        if self.return_id and self.picking_type_id.code == 'incoming':
            self._assign_setsco_serials_from_return()
            
        return result

    def action_assign(self):
        """Override to handle setsco serial assignment after move lines are created"""
        result = super().action_assign()
        
        # After action_assign, assign setsco serials if this is a return picking
        # Only process incoming pickings (returns) that have a return_id
        # Skip if already processed in action_confirm
        if self.return_id and self.picking_type_id.code == 'incoming':
            # Check if any move lines already have setsco serials assigned
            has_setsco_serials = any(ml.setsco_serial_ids for ml in self.move_line_ids)
            if not has_setsco_serials:
                _logger.info(f"Processing return assignment for picking {self.name} in action_assign")
                self._assign_setsco_serials_from_return()
            
        return result
    
    def _assign_setsco_serials_from_return(self):
        """Assign setsco serials from original delivery to return move lines"""
        _logger.info("=== Starting setsco serial return assignment ===")
        
        # Get the original delivery picking
        original_picking = self.return_id
        
        if not original_picking:
            _logger.info("No original picking found")
            return
            
        _logger.info(f"Original picking: {original_picking.name}, type: {original_picking.picking_type_id.code}")
        
        if original_picking.picking_type_id.code != 'outgoing':
            _logger.info("Skipping: not an outgoing delivery")
            return
     
        
        # If no move lines exist yet, try to create them from moves
        if not self.move_line_ids and self.move_ids:
            _logger.info("No move lines found, but moves exist. Creating move lines...")
            for move in self.move_ids:
                if move.product_id.requires_setsco_serial:
                    # Create a basic move line for this move
                    move_line_vals = {
                        'move_id': move.id,
                        'picking_id': self.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'quantity': move.product_uom_qty,
                        'qty_done': 0,
                    }
                    self.env['stock.move.line'].create(move_line_vals)
                    _logger.info(f"Created move line for move {move.id}")
        
        # Refresh move lines after potential creation
        self.invalidate_recordset(['move_line_ids'])
        
        # Wait a bit for move lines to be fully created if they don't exist yet
        if not self.move_line_ids:
            _logger.info("No move lines found yet, waiting for creation...")
            return
        
        # Group move lines by product and lot for better handling
        move_lines_by_product = {}
        for move_line in self.move_line_ids:
            if not move_line.product_id.requires_setsco_serial:
                _logger.info(f"Skipping move line for product {move_line.product_id.name} - doesn't require setsco serials")
                continue
                
            product_key = move_line.product_id.id
            if product_key not in move_lines_by_product:
                move_lines_by_product[product_key] = []
            move_lines_by_product[product_key].append(move_line)
        
        _logger.info(f"Products requiring setsco serials: {len(move_lines_by_product)}")
        
        for product_id, move_lines in move_lines_by_product.items():
            product = self.env['product.product'].browse(product_id)
            _logger.info(f"Processing product: {product.name}")
            
            History = self.env['setsco.serial.move.line.history']

            shipped_hist = History.search([
                ('picking_id', '=', original_picking.id),
                ('picking_type_code', '=', 'outgoing'),
                ('event', '=', 'done'),
                ('setsco_serial_id.product_id', '=', product_id),
                ('setsco_serial_id.state', '=', 'delivered'),
            ])
            delivered_serials = shipped_hist.mapped('setsco_serial_id')

            if not delivered_serials:
                # Fallback for legacy data (before history existed / before backfill ran)
                delivered_serials = self.env['setsco.serial.number'].search([
                    '|', '|',
                    ('delivery_picking_id', '=', original_picking.id),
                    ('delivery_move_line_id.picking_id', '=', original_picking.id),
                    ('move_line_id.picking_id', '=', original_picking.id),
                    ('product_id', '=', product_id),
                    ('state', '=', 'delivered')
                ])

            # Only allow serials whose latest outgoing delivery is this original_picking
            if delivered_serials:
                last_outgoing_hist = History.search([
                    ('setsco_serial_id', 'in', delivered_serials.ids),
                    ('picking_type_code', '=', 'outgoing'),
                    ('event', '=', 'done'),
                ], order='date desc, id desc')
                latest_by_serial = {}
                for h in last_outgoing_hist:
                    sid = h.setsco_serial_id.id
                    if sid not in latest_by_serial:
                        latest_by_serial[sid] = h.picking_id.id

                delivered_serials = delivered_serials.filtered(
                    lambda s: latest_by_serial.get(s.id) == original_picking.id
                ).sorted(key=lambda s: s.name or '')
            
            _logger.info(f"Found {len(delivered_serials)} delivered serials for product {product.name}")
            
            if not delivered_serials:
                _logger.info(f"No delivered serials found for product {product.name}")
                continue
            
            # Calculate total return quantity for this product
            total_return_qty = sum(int(ml.quantity) for ml in move_lines)
            _logger.info(f"Total return quantity: {total_return_qty}")
            
            # Take the first N serials based on return quantity
            serials_to_return = delivered_serials[:total_return_qty]
            _logger.info(f"Serials to return: {len(serials_to_return)}")
            
            if not serials_to_return:
                _logger.info(f"No serials selected for return")
                continue
            
            # Group serials by lot
            lot_groups = {}
            for serial in serials_to_return:
                lot_id = serial.lot_id.id if serial.lot_id else False
                if lot_id not in lot_groups:
                    lot_groups[lot_id] = []
                lot_groups[lot_id].append(serial)
            
            _logger.info(f"Lot groups: {len(lot_groups)}")
            for lot_id, serials in lot_groups.items():
                _logger.info(f"  Lot {lot_id}: {len(serials)} serials")
            
            # Clear existing move lines for this product
            for move_line in move_lines:
                move_line.unlink()
            
            # Create new move lines for each lot
            original_move = self.move_ids.filtered(lambda m: m.product_id.id == product_id)[:1]
            if not original_move:
                _logger.error(f"No move found for product {product.name}")
                continue
            
            _logger.info(f"Using original move: {original_move.id}")
            
            for lot_id, serials in lot_groups.items():
                _logger.info(f"Creating move line for lot {lot_id} with {len(serials)} serials")
                
                move_line_vals = {
                    'move_id': original_move.id,
                    'picking_id': self.id,
                    'product_id': product_id,
                    'product_uom_id': original_move.product_uom.id,
                    'location_id': original_move.location_id.id,
                    'location_dest_id': original_move.location_dest_id.id,
                    'lot_id': lot_id,
                    'quantity': len(serials),
                    'qty_done': len(serials),
                }
                
                new_move_line = self.env['stock.move.line'].create(move_line_vals)
                _logger.info(f"Created move line {new_move_line.id}")
                
                # Assign serials to this move line
                # Note: Don't change state here - state will be changed to 'warehouse' 
                # when the picking is validated in button_validate()
                for serial in serials:
                    serial.write({
                        'move_line_id': new_move_line.id,
                        # State will be updated in button_validate when picking is validated
                    })
                    _logger.info(f"Assigned serial {serial.name} to move line {new_move_line.id}")
                
                _logger.info(f"Created move line {new_move_line.id} for lot {lot_id} with {len(serials)} serials")
        
        _logger.info("=== Finished setsco serial return assignment ===")


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _create_return_move(self, return_picking_id, location_id, location_dest_id, product_qty):
        """Override to handle setsco serial returns properly"""
        # Call parent method
        result = super()._create_return_move(return_picking_id, location_id, location_dest_id, product_qty)
        
        return result 