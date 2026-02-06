from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import ast

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    requires_setsco_serial = fields.Boolean(string='Requires setsco Serial',
                                            compute='_compute_requires_setsco_serial')
    setsco_serial_ids = fields.One2many('stock.move.line', 'move_id',
                                        string='Setsco Serial Numbers',
                                        domain=[('setsco_serial_ids', '!=', False)])
    to_remove_lst = fields.Char(string="to_remove")

    @api.model_create_multi
    def create(self, vals_list):
        clean_vals = []
        for vals in vals_list:
            product_id = vals.get('product_id')
            raw_material_production_id = vals.get('raw_material_production_id')

            if not product_id or raw_material_production_id or self.env['stock.picking.type'].browse(vals.get('picking_type_id')).code != 'internal':
                # Keep if no product or not a production move
                clean_vals.append(vals)
                continue

            product = self.env['product.product'].browse(product_id)


            # always ensure 0 for quantity_requested whencreate
            vals['quantity_requested'] = 0

            if not product.categ_id.is_setsco_label:
                clean_vals.append(vals)


        return super().create(clean_vals)
    def _check_setsco_label_and_unlink(self):
        """Custom logic: remove move_dest if is_setsco_label is found."""
        for rec in self:
            if (
                    rec.raw_material_production_id and
                    rec.product_id.categ_id.is_setsco_label and
                    rec.quantity != rec.product_uom_qty
            ):
                rec.quantity = rec.product_uom_qty
                return

    def write(self, vals):
        res = super().write(vals)

        self._check_setsco_label_and_unlink()
        
        # Enhanced location tracking for setsco serials
        if 'state' in vals:
            self._update_setsco_serial_locations_from_moves(vals)

        return res

    def _update_setsco_serial_locations_from_moves(self, vals):
        """Update setsco serial locations when stock moves change"""
        for move in self:
            if not move.requires_setsco_serial:
                continue
                
            # Update locations for all setsco serials in move lines
            for move_line in move.move_line_ids:
                if move_line.setsco_serial_ids:
                    for serial in move_line.setsco_serial_ids:
                        # Update location based on move changes
                        if 'location_id' in vals or 'location_dest_id' in vals:
                            serial._update_location_from_stock_move(move)
                        elif 'state' in vals:
                            serial._update_location_from_stock_move(move)

    @api.depends('product_id.requires_setsco_serial')
    def _compute_requires_setsco_serial(self):
        for move in self:
            move.requires_setsco_serial = move.product_id.requires_setsco_serial

    def _action_assign(self, force_qty=False):
        """Override to check setsco serial requirements"""
        result = super()._action_assign()
        
        for move in self:
            if move.requires_setsco_serial and move.picking_type_id.code in ['outgoing', 'internal']:
                # Check if setsco serials are assigned for outgoing moves
                if not any(ml.setsco_serial_ids for ml in move.move_line_ids):
                    move.write({'state': 'partially_available'})
        
        return result

    def action_select_setsco_serials_range(self):
        """Open wizard to select setsco serials in range"""
        if not self.requires_setsco_serial:
            return

        # Detect if this is a return picking
        is_return = False
        picking = self.picking_id
        if picking and picking.picking_type_id.code == 'incoming' and picking.return_id:
            is_return = True

        return {
            'name': _('Select Setsco Serial Range'),
            'type': 'ir.actions.act_window',
            'res_model': 'setsco.serial.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.product_id.id,
                'default_move_id': self.id,  # Pass move ID instead of move_line_id
                'default_quantity': 0,
                'default_is_return': is_return,
            }
        }
    
    def _update_move_lot_ids_from_lines(self):
        """Update move lot_ids based on all move lines' lots from setsco serials"""
        if not self.move_line_ids:
            return
            
        # Get all lots from all move lines with setsco serials
        all_lots = []
        for move_line in self.move_line_ids:
            if move_line.setsco_serial_ids:
                lot_ids = move_line.setsco_serial_ids.mapped('lot_id').filtered(lambda l: l).ids
                all_lots.extend(lot_ids)
            elif move_line.lot_id:
                # Also include lots directly assigned to move lines
                all_lots.append(move_line.lot_id.id)
        
        # Remove duplicates and update move lot_ids
        unique_lot_ids = list(set(all_lots))
        if unique_lot_ids:
            self.write({'lot_ids': [(6, 0, unique_lot_ids)]})
        else:
            self.write({'lot_ids': [(6, 0, [])]}) 

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    picking_code = fields.Selection(
        related='picking_id.picking_type_id.code',
        store=True,
        readonly=True,
        help='Picking type code (related) for safe view modifiers.',
    )
    picking_state = fields.Selection(
        related='picking_id.state',
        store=True,
        readonly=True,
        help='Picking state (related) for safe view modifiers.',
    )

    setsco_serial_ids = fields.One2many('setsco.serial.number', 'move_line_id',
                                       string='Setsco Serial Numbers')
    delivered_setsco_serial_ids = fields.One2many(
        'setsco.serial.number',
        'delivery_move_line_id',
        string='Delivered Setsco Serials',
        readonly=True,
        help='Historical delivered serials for this move line (kept even after returns).',
    )
    display_setsco_serial_ids = fields.Many2many(
        'setsco.serial.number',
        compute='_compute_display_setsco_serial_ids',
        string='Setsco Serials (Display)',
        readonly=True,
        help='Shows delivered serials on done outgoing pickings; otherwise shows current selection.',
    )

    setsco_name = fields.Char(string='Setsco Name', compute='_compute_setsco_name')
    requires_setsco_serial = fields.Boolean(string='Requires Setsco Serial',
                                            related='move_id.requires_setsco_serial')
    setsco_serial_count = fields.Integer(string='Setsco Serial Count',
                                        compute='_compute_setsco_serial_count')

    @api.depends('setsco_serial_ids', 'delivered_setsco_serial_ids', 'picking_code', 'picking_state')
    def _compute_display_setsco_serial_ids(self):
        History = self.env['setsco.serial.move.line.history']
        for line in self:
            if line.picking_code == 'outgoing' and line.picking_state == 'done':
                hist = History.search([
                    ('move_line_id', '=', line.id),
                    ('picking_type_code', '=', 'outgoing'),
                    ('event', '=', 'done'),
                ])
                shipped = hist.mapped('setsco_serial_id')
                # Fallback for older deliveries not yet backfilled
                line.display_setsco_serial_ids = shipped or line.delivered_setsco_serial_ids or line.setsco_serial_ids
            else:
                line.display_setsco_serial_ids = line.setsco_serial_ids

    def _compute_setsco_name(self):
        for line in self:
            line.setsco_name = ', '.join(line.display_setsco_serial_ids.mapped('name'))
                    
    @api.depends('product_id', 'setsco_serial_ids')
    def _compute_display_name(self):
        for move in self:
            if move.requires_setsco_serial:
                move.display_name = '%s' % (', '.join(move.display_setsco_serial_ids.mapped('name')))
            else:
                move.display_name = move.product_id.display_name


    @api.depends('setsco_serial_ids')
    def _compute_setsco_serial_count(self):
        for line in self:
            line.setsco_serial_count = len(line.display_setsco_serial_ids)

    @api.onchange('setsco_serial_ids')
    def _onchange_setsco_serial_ids(self):
        """Validate setsco serials and update quantity"""
        if self.setsco_serial_ids:
            # Check that all serials are in warehouse state (came from manufacturing)
            non_warehouse_serials = self.setsco_serial_ids.filtered(lambda s: s.state != 'warehouse')
            if non_warehouse_serials:
                # Reset the serials that are not in warehouse state
                self.setsco_serial_ids = [(6, 0, self.setsco_serial_ids.filtered(lambda s: s.state == 'warehouse').ids)]
                return {
                    'warning': {
                        'title': _('Invalid Serial Selection'),
                        'message': _('Only warehouse state serials (from completed manufacturing) can be selected for delivery. '
                                   'Invalid serials have been automatically removed.')
                    }
                }
            
            # Check that all serials are in the source location
            if self.location_id:
                wrong_location_serials = self.setsco_serial_ids.filtered(lambda s: s.location_id != self.location_id)
                if wrong_location_serials:
                    # Reset the serials that are not in the correct location
                    correct_location_serials = self.setsco_serial_ids.filtered(lambda s: s.location_id == self.location_id)
                    self.setsco_serial_ids = [(6, 0, correct_location_serials.ids)]
                    return {
                        'warning': {
                            'title': _('Invalid Location'),
                            'message': _('Some serials are not available in the source location (%s). '
                                       'Only serials from the correct location have been selected.') % self.location_id.name
                        }
                    }
            
            # Update quantity to match serial count
            if len(self.setsco_serial_ids) != self.quantity:
                self.quantity = len(self.setsco_serial_ids)

    @api.constrains('setsco_serial_ids', 'quantity')
    def _check_setsco_serial_quantity(self):
        for line in self:
            return
            if line.setsco_serial_ids and line.product_uom_quantity != len(line.setsco_serial_ids):
                raise ValidationError(_('Product quantity (%d) must match number of setsco serial numbers (%d)')
                                    % (line.quantity, len(line.setsco_serial_ids)))

    @api.constrains('setsco_serial_ids', 'location_id')
    def _check_setsco_serial_location(self):
        for line in self:
            # Temporary return
            return
            if line.setsco_serial_ids and line.location_id:
                wrong_location_serials = line.setsco_serial_ids.filtered(lambda s: s.location_id != line.location_id)
                if wrong_location_serials:
                    raise ValidationError(_('Setsco serial numbers must be in the source location (%s). '
                                          'Invalid serials: %s') % 
                                        (line.location_id.name, ', '.join(wrong_location_serials.mapped('name'))))

    def write(self, vals):
        result = super().write(vals)
        
        # Update parent move lot_ids when setsco serials change
        if 'setsco_serial_ids' in vals or any(key.startswith('setsco_serial_ids') for key in vals.keys()):
            for line in self:
                if line.move_id:
                    line.move_id._update_move_lot_ids_from_lines()
        
        # Enhanced location tracking for setsco serials
        self._update_setsco_serial_locations(vals)
        
        return result

    def _update_setsco_serial_locations(self, vals):
        """Comprehensive location update for setsco serial numbers"""
        for line in self:
      
            if not line.setsco_serial_ids:
                continue
    
            # Update locations based on different scenarios
            if 'qty_done' in vals:
                # When quantity is done, update to destination location
                if vals.get('qty_done', 0) > 0 and line.location_dest_id:
                    for serial in line.setsco_serial_ids:
                        serial._update_location_from_move_line(line)
                        
            elif 'location_id' in vals:
                # When source location changes, update serial locations
                for serial in line.setsco_serial_ids:
                    serial._update_location_from_move_line(line)
                    
            elif 'location_dest_id' in vals:
                # When destination location changes, prepare for future moves
                for serial in line.setsco_serial_ids:
                    serial._update_location_from_move_line(line)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to update move lot_ids when move lines are created with setsco serials"""
        lines = super().create(vals_list)
        
        for line in lines:
            if line.setsco_serial_ids and line.move_id:
                line.move_id._update_move_lot_ids_from_lines()
                # Update initial locations for newly created move lines
                line._update_setsco_serial_locations({})
        
        return lines

    def action_select_setsco_serials_range(self):
        """Open wizard to select multiple setsco serial numbers"""
        if not self.product_id.requires_setsco_serial:
            return
        
        # Detect if this is a return picking
        is_return = False
        picking = self.picking_id or (self.move_id and self.move_id.picking_id)
        if picking and picking.picking_type_id.code == 'incoming' and picking.return_id:
            is_return = True
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Serial Numbers'),
            'res_model': 'setsco.serial.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_quantity': max(1, int(self.quantity)),
                'default_is_return': is_return,
            }
        }

    #this function is to auto assign the setsco once production done
    def _assign_setsco_move_line(self):
        for rec in self:
            setsco_number = False
            
            # Method 1: Try lot-based assignment (existing logic)
            if rec.lot_id and rec.location_id.id:
                setsco_number = self.env['setsco.serial.number']._get_setsco_serial_from_lot(rec.lot_id.id, rec.location_id.id)
            production = rec.move_id.raw_material_production_id
            # Method 2: Fallback - Production-based assignment when no lot
            if not setsco_number and rec.move_id.raw_material_production_id:

                # Find Setsco serials assigned to this production that are in warehouse state
                setsco_number = self.env['setsco.serial.number'].search([
                    ('production_id', '=', production.id),
                    ('product_id', '=', rec.product_id.id),
                    ('state', '=', 'warehouse'),  
                ], limit=1)
            
            # Method 3: Fallback - Location and product-based assignment
            if not setsco_number and rec.location_id.id:
                setsco_number = self.env['setsco.serial.number'].search([
                    ('product_id', '=', rec.product_id.id),
                    ('location_id', '=', rec.location_id.id),
                    ('state', '=', 'warehouse'),
            
                ], limit=1)
            
            # Assign the found Setsco serial to the move line
            if setsco_number:
                setsco_number.write({'move_line_id': rec.id})
                _logger.info(f"Assigned Setsco serial {setsco_number.name} to move line {rec.id}")
            else:
                _logger.warning(f"No Setsco serial found for move line {rec.id} (Product: {rec.product_id.name}, Location: {rec.location_id.name})")

    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + ['requires_setsco_serial','setsco_name']

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    has_setsco_serials = fields.Boolean(string='Has Setsco Serial Numbers',
                                        compute='_compute_has_setsco_serials')
    setsco_serial_count = fields.Integer(string='Setsco Serial Count',
                                         compute='_compute_setsco_serial_count')

    @api.depends('move_line_ids.setsco_serial_ids', 'move_line_ids.display_setsco_serial_ids', 'picking_type_id.code', 'state')
    def _compute_has_setsco_serials(self):
        for picking in self:
            if picking.picking_type_id.code == 'outgoing' and picking.state == 'done':
                picking.has_setsco_serials = any(ml.display_setsco_serial_ids for ml in picking.move_line_ids)
            else:
                picking.has_setsco_serials = any(ml.setsco_serial_ids for ml in picking.move_line_ids)

    @api.depends('move_line_ids.setsco_serial_ids', 'move_line_ids.display_setsco_serial_ids', 'picking_type_id.code', 'state')
    def _compute_setsco_serial_count(self):
        for picking in self:
            if picking.picking_type_id.code == 'outgoing' and picking.state == 'done':
                picking.setsco_serial_count = sum(len(ml.display_setsco_serial_ids) for ml in picking.move_line_ids)
            else:
                picking.setsco_serial_count = sum(len(ml.setsco_serial_ids) for ml in picking.move_line_ids)

    def action_view_setsco_serials(self):
        """View setsco serial numbers for this picking"""
        self.ensure_one()
        serial_ids = []
        for ml in self.move_line_ids:
            if self.picking_type_id.code == 'outgoing' and self.state == 'done':
                serial_ids.extend(ml.display_setsco_serial_ids.ids)
            else:
                serial_ids.extend(ml.setsco_serial_ids.ids)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Picking Setsco Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('id', 'in', serial_ids)],
            'context': {'create': False}
        }

    def action_backfill_setsco_history(self, limit=0):
        """Backfill `setsco.serial.move.line.history` for existing done pickings.

        This is **best-effort**. For old outgoing deliveries where the serials were later
        re-linked to returns (so `move_line_id` no longer points to the original DO move
        line), recovery is only possible if `setsco.serial.number.delivery_picking_id`
        and `delivery_move_line_id` were already populated.

        Usage examples (Odoo shell):
        - Backfill for a specific picking:
          `env['stock.picking'].browse(PICKING_ID).action_backfill_setsco_history()`
        - Backfill last N done pickings (call on empty recordset):
          `env['stock.picking'].browse().action_backfill_setsco_history(limit=500)`
        """
        History = self.env['setsco.serial.move.line.history']
        Serial = self.env['setsco.serial.number']

        pickings = self
        if not pickings:
            dom = [('state', '=', 'done')]
            if limit:
                pickings = self.search(dom, order='id desc', limit=limit)
            else:
                pickings = self.search(dom, order='id desc')

        for picking in pickings:
            if picking.state != 'done' or not picking.picking_type_id:
                continue

            picking_type_code = picking.picking_type_id.code
            date_done = getattr(picking, 'date_done', False) or fields.Datetime.now()

            # Outgoing: prefer delivery_* snapshot, since move_line_id may have been overwritten by returns.
            if picking_type_code == 'outgoing':
                serials = Serial.search([
                    ('delivery_picking_id', '=', picking.id),
                    ('delivery_move_line_id', '!=', False),
                ])

                # Also include any serials still currently linked to this DO (no return overwrite)
                serials |= Serial.search([('move_line_id.picking_id', '=', picking.id)])

                for serial in serials:
                    ml = serial.delivery_move_line_id or serial.move_line_id
                    if not ml or not ml.exists() or ml.picking_id.id != picking.id:
                        continue

                    existing = History.search([
                        ('move_line_id', '=', ml.id),
                        ('event', '=', 'done'),
                        ('setsco_serial_id', '=', serial.id),
                    ], limit=1)
                    if existing:
                        continue

                    History.create([{
                        'setsco_serial_id': serial.id,
                        'move_line_id': ml.id,
                        'picking_id': picking.id,
                        'picking_type_code': 'outgoing',
                        'event': 'done',
                        'date': date_done,
                        'company_id': picking.company_id.id,
                    }])

                continue

            # Incoming/Internal: move lines still carry the current setsco_serial_ids.
            if picking_type_code in ('incoming', 'internal'):
                for ml in picking.move_line_ids:
                    if not ml.setsco_serial_ids:
                        continue

                    existing_hist = History.search([
                        ('move_line_id', '=', ml.id),
                        ('event', '=', 'done'),
                        ('setsco_serial_id', 'in', ml.setsco_serial_ids.ids),
                    ])
                    existing_ids = set(existing_hist.mapped('setsco_serial_id').ids)

                    to_create = []
                    for s in ml.setsco_serial_ids:
                        if s.id in existing_ids:
                            continue
                        to_create.append({
                            'setsco_serial_id': s.id,
                            'move_line_id': ml.id,
                            'picking_id': picking.id,
                            'picking_type_code': picking_type_code,
                            'event': 'done',
                            'date': date_done,
                            'company_id': picking.company_id.id,
                        })
                    if to_create:
                        History.create(to_create)

        return True

    def action_create_invoice(self):
        """Override to assign created invoice to setsco serial numbers"""
        # Get setsco serials that need invoice assignment before creating invoice
        setsco_serials_to_update = []
        for move in self.move_ids:
            if move.requires_setsco_serial and self.picking_type_id.code in ['outgoing', 'internal']:
                for move_line in move.move_line_ids:
                    if move_line.setsco_serial_ids:
                        setsco_serials_to_update.extend(move_line.setsco_serial_ids.ids)
        
        # Call parent method to create invoice
        result = super().action_create_invoice()
        
        # After invoice creation, assign it to setsco serial numbers
        if setsco_serials_to_update and self.invoice_id:
            serials = self.env['setsco.serial.number'].browse(setsco_serials_to_update)
            serials.write({'invoice_id': self.invoice_id.id, 'picking_id':self.id})
            _logger.info(f'Assigned invoice {self.invoice_id.name} to {len(serials)} setsco serial numbers')
        
        return result

    def button_validate(self):
        """Override to validate setsco serial requirements and update serial states"""
        # Check if all required setsco serials are assigned before validation
        # Skip this check for incoming moves (returns) as serials are assigned during action_assign

        setsco_serials_to_update = {}
        for move in self.move_ids:
            if move.requires_setsco_serial:
                # For outgoing/internal, check that serials are assigned
                if self.picking_type_id.code in ['outgoing', 'internal']:
                    unassigned_lines = move.move_line_ids.filtered(
                        lambda ml: not ml.setsco_serial_ids and ml.quantity > 0
                    )
                    if unassigned_lines:
                        raise ValidationError(_('Please assign setsco serial numbers for all move lines of product %s') %
                                            move.product_id.name)

                # Collect setsco serials for all picking types (outgoing, internal, incoming)
                for move_line in move.move_line_ids:
                    if move_line.setsco_serial_ids:
                        setsco_serials_to_update[move_line.id] = {
                            'serials': move_line.setsco_serial_ids.ids,
                            'picking_type': self.picking_type_id.code
                        }
        
        # Call parent validation
        result = super().button_validate()
        
        History = self.env['setsco.serial.move.line.history']

        # After successful validation, update setsco serial states and assign invoices
        for move_line_id, data in setsco_serials_to_update.items():
            serials = self.env['setsco.serial.number'].browse(data['serials'])

            # Log a durable history row for traceability (deliver → return → deliver again)
            existing_hist = History.search([
                ('move_line_id', '=', move_line_id),
                ('event', '=', 'done'),
                ('setsco_serial_id', 'in', serials.ids),
            ])
            existing_serial_ids = set(existing_hist.mapped('setsco_serial_id').ids)
            to_create = []
            for s in serials:
                if s.id in existing_serial_ids:
                    continue
                to_create.append({
                    'setsco_serial_id': s.id,
                    'move_line_id': move_line_id,
                    'picking_id': self.id,
                    'picking_type_code': self.picking_type_id.code,
                    'event': 'done',
                    'date': fields.Datetime.now(),
                    'company_id': self.company_id.id,
                })
            if to_create:
                History.create(to_create)
            
            # Update locations for all serials based on picking completion
            for serial in serials:
                serial._update_location_from_picking(self)
            
            # Assign invoice to setsco serial numbers for outgoing deliveries
            if data['picking_type'] == 'outgoing':
                # Preserve delivery history so the original delivery move line keeps its serials
                serials.write({
                    'delivery_picking_id': self.id,
                    'delivery_move_line_id': move_line_id,
                })

                # Find related invoice for this picking
                related_invoice = self._find_related_invoice()
                if related_invoice:
                    serials.write({'invoice_id': related_invoice.id})
                    _logger.info(f'Assigned invoice {related_invoice.name} to {len(serials)} setsco serial numbers')
                
                # Mark as delivered
                for serial in serials:
                    serial.action_set_delivered()
            elif data['picking_type'] == 'incoming':
                # Return from customer or receipt - mark as warehouse
                for serial in serials:
                    serial.action_set_warehouse()
                    # Update location to stock location for returns
                    stock_location = self.env['stock.location'].search([
                        ('usage', '=', 'internal'),
                        ('name', '=', 'Stock')
                    ], limit=1)
                    if stock_location and serial.location_id != stock_location:
                        old_location = serial.location_id
                        serial.write({'location_id': stock_location.id})
                        if old_location:
                            serial.message_post(
                                body=_('Location updated from %s to %s (stock location) for customer return') % 
                                (old_location.name, stock_location.name)
                            )
            # Note: For returns, serials are already set to warehouse state during action_assign
        
        return result

    def _find_related_invoice(self):
        """Find the related invoice for this picking"""
        # Method 1: Check if picking is linked to a sale order with invoice
        if self.sale_id:
            invoices = self.sale_id.invoice_ids.filtered(
                lambda inv: inv.state in ['posted', 'draft'] and inv.move_type == 'out_invoice'
            )
            if invoices:
                return invoices[0]  # Return the first invoice
        
        # Method 2: Check if picking is linked to a delivery order with invoice
        if self.purchase_id:
            invoices = self.purchase_id.invoice_ids.filtered(
                lambda inv: inv.state in ['posted', 'draft'] and inv.move_type == 'in_invoice'
            )
            if invoices:
                return invoices[0]  # Return the first invoice
        
        # Method 3: Check if there's a direct invoice reference in picking
        if hasattr(self, 'invoice_id') and self.invoice_id:
            return self.invoice_id
        
        # Method 4: Search for invoices by partner and date range
        if self.partner_id:
            # Look for invoices created around the same time as the picking
            picking_date = self.scheduled_date or self.create_date
            if picking_date:
                # Search for invoices within 7 days of picking date
                from datetime import timedelta
                date_from = picking_date - timedelta(days=7)
                date_to = picking_date + timedelta(days=7)
                
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', 'in', ['posted', 'draft']),
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<=', date_to)
                ], order='invoice_date desc', limit=1)
                
                if invoices:
                    return invoices[0]
        
        return False



class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _gather(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, qty=0):
        """Override to consider setsco serial numbers in stock gathering"""
        quants = super()._gather(product_id, location_id, lot_id, package_id, owner_id, strict)

        # Additional filtering could be added here if needed for setsco serials
        return quants

    def move_quants(self, location_dest_id=False, package_dest_id=False, message=False, unpack=False):
        '''
        This function is to update the location of the setsco serial numbers when the quant is moved
        '''
        result = super().move_quants(location_dest_id, package_dest_id, message, unpack)

        for quant in self:
            self.env['setsco.serial.number'].search([
                ('location_id', '=', quant.location_id.id),
                ('product_id', '=', quant.product_id.id),
            ]).write({'location_id': location_dest_id.id})
        return result