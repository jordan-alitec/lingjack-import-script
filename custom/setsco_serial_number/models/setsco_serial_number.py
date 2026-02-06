from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)


class SetscoSerialNumber(models.Model):
    _name = 'setsco.serial.number'
    _description = 'Setsco Serial Number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'
    _rec_name = 'name'

    name = fields.Char(string='Serial Number', required=True, index=True, copy=False)
    sequence = fields.Char(string='Sequence', readonly=True, copy=False)
    active = fields.Boolean(string='Active', default=True)

    # Type Information
    serial_type = fields.Selection([
        ('tuv', 'TUV'),
        ('setsco', 'Setsco')
    ], string='Serial Type', required=True, default='setsco', tracking=True,
       help='Type of serial number: TUV or Setsco')
    
    # Basic Information - Now category-based
    category_id = fields.Many2one('product.category', string='Product Category', required=False,
                                  help='Product category this serial number is associated with')
    setsco_category_id = fields.Many2one('setsco.category', string='Serial Category', required=True,
                                         help='Serial category this serial number is linked to')
    product_id = fields.Many2one('product.product', string='Product', required=False,
                                 help='Specific product this serial is assigned to (optional)')
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', 
                                      related='product_id.product_tmpl_id', store=True)
    
    # State Management
    state = fields.Selection([
        ('new', 'On hand'),
        ('manufacturing', 'In Manufacturing'),
        ('warehouse', 'Finished Goods'),
        ('delivered', 'Delivered'),
        ('scrapped', 'Scrapped')
    ], string='State', default='new', required=True, tracking=True)
    
    # Purchase Information
    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Purchase Order Line')
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order',domain="[('has_setsco_serials', '=', True)]")
    vendor_id = fields.Many2one('res.partner', string='Vendor', 
                                related='purchase_order_id.partner_id', store=True)
    purchase_date = fields.Datetime(string='Purchase Date', 
                                    related='purchase_order_id.date_order', store=True)
    
    # Manufacturing Information
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    lot_id = fields.Many2one('stock.lot', string='Odoo Lot/Serial Number')
    manufacturing_date = fields.Datetime(string='Manufacturing Date')
    
    # Stock Information
    location_id = fields.Many2one('stock.location', string='Current Location')
    move_line_id = fields.Many2one('stock.move.line', string='Stock Move Line')
    picking_id = fields.Many2one('stock.picking', string='Delivery Order', 
                                compute='_compute_picking_id', store=True)

    # Delivery history (do NOT change when returns re-link move_line_id)
    delivery_picking_id = fields.Many2one(
        'stock.picking',
        string='Delivered Picking',
        readonly=True,
        copy=False,
        help='Outgoing delivery order where this serial was delivered (historical).',
    )
    delivery_move_line_id = fields.Many2one(
        'stock.move.line',
        string='Delivered Move Line',
        readonly=True,
        copy=False,
        help='Outgoing move line where this serial was delivered (historical).',
    )
    
    # Invoice Information
    invoice_id = fields.Many2one('account.move', string='Invoice', 
                                 domain="[('move_type', 'in', ['out_invoice', 'out_refund'])]",
                                 help='Invoice associated with this serial number')
    invoice_number = fields.Char(string='Invoice Number', 
                                 related='invoice_id.name', store=True,
                                 help='Invoice number for this serial number')
    
    # Traceability
    company_id = fields.Many2one('res.company', string='Company', 
                                 default=lambda self: self.env.company)
    notes = fields.Text(string='Notes')
    
    # Dates
    delivery_date = fields.Datetime(string='Delivery Date')
    return_date = fields.Datetime(string='Return Date')
    scrap_date = fields.Datetime(string='Scrap Date')
    
    # Computed Fields
    is_available = fields.Boolean(string='Available', compute='_compute_is_available', store=True)
    current_owner = fields.Many2one('res.partner', string='Current Owner', compute='_compute_current_owner')
    stock_move_count = fields.Integer(string='Stock Move Count', compute='_compute_stock_move_count')
    qr_code_value = fields.Text(string='QR Code Value', compute='_compute_qr_code_value', store=True)


    # Internal Company Transactions
    tranfered_to_internal_company = fields.Boolean(string='Tranfered to Internal Company', default=False)
    internal_company_id = fields.Many2one('res.company', string='Internal Company', default=lambda self: self.env.company)
    internal_delivery_order_ref = fields.Many2one('stock.picking', string='Picking')
    internal_delivery_order_date = fields.Datetime(string='Assigned Date')
    
    # Reverse Transfer Tracking Fields
    previous_state = fields.Selection([
        ('new', 'On hand'),
        ('manufacturing', 'In Manufacturing'),
        ('warehouse', 'Finished Goods'),
        ('delivered', 'Delivered'),
        ('scrapped', 'Scrapped')
    ], string='Previous State', help='State before last transfer operation')
    previous_internal_company_id = fields.Many2one('res.company', string='Previous Internal Company', 
                                                  help='Internal company before last transfer')
    previous_location_id = fields.Many2one('stock.location', string='Previous Location',
                                          help='Location before last transfer')
    previous_product_id = fields.Many2one('product.product', string='Previous Product',
                                         help='Product before last transfer')
    
    # Original state tracking for multiple reversals
    original_state = fields.Selection([
        ('new', 'On hand'),
        ('manufacturing', 'In Manufacturing'),
        ('warehouse', 'Finished Goods'),
        ('delivered', 'Delivered'),
        ('scrapped', 'Scrapped')
    ], string='Original State', help='Original state before any transfer operations')
    original_internal_company_id = fields.Many2one('res.company', string='Original Internal Company',
                                                   help='Original internal company before any transfers')
    original_location_id = fields.Many2one('stock.location', string='Original Location',
                                          help='Original location before any transfers')
    original_product_id = fields.Many2one('product.product', string='Original Product',
                                         help='Original product before any transfers')
    
    can_reverse = fields.Boolean(string='Can Reverse', compute='_compute_can_reverse',
                                help='Whether this serial can be reversed to previous state')

    # @api.constrains('location_id')
    # def _check_location_id(self):
    #      asd = asd


    def _get_setsco_serial_from_lot(self, lot_id, location_id):
        return self.env['setsco.serial.number'].search([('lot_id', '=', lot_id),('location_id','=',location_id)])

    @api.depends('previous_state', 'original_state')
    def _compute_can_reverse(self):
        """Compute whether this serial can be reversed to previous state"""
        for record in self:
            # Can reverse if there's a previous state OR an original state
            # This allows multiple reversals: previous -> original -> previous -> original
            record.can_reverse = bool(record.previous_state or record.original_state)

    def action_reverse_transfer(self):
        """Reverse the last transfer operation (both transfer out and receive back)"""
        self.ensure_one()
        
        if not self.can_reverse:
            raise UserError(_('This serial number cannot be reversed. No previous or original state available.'))
        
        # Determine which state to reverse to
        if self.previous_state:
            # Reverse to previous state
            target_state = self.previous_state
            target_company = self.previous_internal_company_id
            target_location = self.previous_location_id
            target_product = self.previous_product_id
            reversal_type = 'previous'
        elif self.original_state:
            # Reverse to original state
            target_state = self.original_state
            target_company = self.original_internal_company_id
            target_location = self.original_location_id
            target_product = self.original_product_id
            reversal_type = 'original'
        else:
            raise UserError(_('No previous or original state found to reverse to.'))
        
        # Store current values for logging
        current_state = self.state
        current_company = self.internal_company_id
        current_location = self.location_id
        current_product = self.product_id
        
        # Determine the appropriate transfer flag based on target state
        if target_state == 'manufacturing':
            # Reversing to manufacturing state - set transfer flag
            transfer_flag = True
        else:
            # Reversing to new/warehouse state - clear transfer flag
            transfer_flag = False
        
        # Reverse to target state
        vals = {
            'state': target_state,
            'internal_company_id': target_company.id if target_company else self.env.company.id,
            'tranfered_to_internal_company': transfer_flag,
        }
        
        # Restore target location if available
        if target_location:
            vals['location_id'] = target_location.id
        
        # Restore target product if available
        if target_product:
            vals['product_id'] = target_product.id
        
        # Update tracking fields for next reversal
        if reversal_type == 'previous':
            # We're reversing to previous state, so next reversal should go to original
            # Keep original state, clear previous state
            vals.update({
                'previous_state': 'New',
                'previous_internal_company_id': False,
                'previous_location_id': False,
                'previous_product_id': False,
            })
        else:
            # We're reversing to original state, so next reversal should go to previous
            # Keep previous state, clear original state
            vals.update({
                'original_state': False,
                'original_internal_company_id': False,
                'original_location_id': False,
                'original_product_id': False,
            })
        
        self.write(vals)
        
        # Log the reversal with appropriate message
        if transfer_flag:
            operation_type = _('receive operation')
        else:
            operation_type = _('transfer operation')
            
        self.message_post(
            body=_('Operation reversed from %s to %s (%s state). Previous state restored after reversing %s.') % 
            (current_state, target_state, reversal_type, operation_type)
        )
      

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence'):
                vals['sequence'] = self.env['ir.sequence'].next_by_code('setsco.serial.number') or '/'
        return super().create(vals_list)

    # def compute_is_available(self):
    #     self._compute_is_available()

    @api.depends('state', 'move_line_id')
    def _compute_is_available(self):
        for record in self:
            record.is_available = record.state in ['new']

    def _compute_current_owner(self):
        for record in self:
            current_owner = False
            if record.state == 'delivered':
                # Find the last delivery
                last_move = record.move_line_id.move_id
                if last_move:
                    current_owner = last_move.picking_id.partner_id
            record.current_owner = current_owner

    def _compute_stock_move_count(self):
        for record in self:
            record.stock_move_count = 1 if record.move_line_id else 0

    @api.depends('move_line_id.picking_id')
    def _compute_picking_id(self):
        for record in self:
            record.picking_id = record.move_line_id.picking_id if record.move_line_id else False

    @api.depends('product_id.default_code', 'production_id.name', 'name', 'production_id.date_start', 'production_id.company_id.name')
    def _compute_qr_code_value(self):
        """Compute the QR code value for label printing"""
        for record in self:
            itemcode = record.product_id.default_code or ''
            pwo = record.production_id.name or ''
            setsco = record.name or ''
            
            # Format manufacturing date
            mfg_date = ''
            if record.production_id and record.production_id.date_start:
                mfg_date = record.production_id.date_start.strftime('%Y%m%d')
            
            company_name = record.production_id.company_id.name or ''
            
            # Create QR code value with newlines
            qr_value = f"ITEMCODE({itemcode})\nPWO({pwo})\nSETSCO({setsco})\nMFG({mfg_date},{company_name})"
            record.qr_code_value = qr_value

    @api.constrains('name', 'category_id')
    def _check_unique_serial_per_category(self):
        for record in self:
            existing = self.search([
                ('name', '=', record.name),
                ('category_id', '=', record.category_id.id),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(_('Serial number %s already exists for category %s') % 
                                    (record.name, record.category_id.name))

    @api.constrains('product_id', 'category_id')
    def _check_product_category_match(self):
        for record in self:
            if record.product_id and record.category_id:
                if record.product_id.categ_id != record.category_id:
                    raise ValidationError(_('Product %s does not belong to category %s') % 
                                        (record.product_id.name, record.category_id.name))

    def action_set_manufacturing(self):
        """Set serial to manufacturing state when assigned to MRP"""
        self.ensure_one()
        if self.state not in ['new', 'warehouse']:
            raise UserError(_('Serial number must be in New or Warehouse state to assign to manufacturing.'))
        self.write({
            'state': 'manufacturing',
            'manufacturing_date': fields.Datetime.now()
        })
    # @api.constrains('location_id')
    # def test(self):
    #     # asd = asd

    def action_set_warehouse(self):
        """Set serial to warehouse state when manufacturing is done or returned"""
        self.ensure_one()
        if self.state not in ['new', 'manufacturing', 'delivered']:
            raise UserError(_('Invalid state transition to warehouse.'))
        
        vals = {'state': 'warehouse'}
        
        # Set return date if coming from delivered state (customer return)
        if self.state == 'delivered':
            vals['return_date'] = fields.Datetime.now()
        
        # Set location if not already set
        if not self.location_id:
            vals['location_id'] = self.env.ref('stock.stock_location_stock').id
            
        self.write(vals)

    def action_set_delivered(self):
        """Set serial to delivered state when shipped to customer"""
        self.ensure_one()
        # if self.state != 'warehouse':
        #     raise UserError(_('Serial number must be in warehouse to be delivered.'))
        self.write({
            'state': 'delivered',
            'delivery_date': fields.Datetime.now()
        })

    def update_location_from_move_line(self):
        """Update location based on the move line's destination location"""
        self.ensure_one()
        if self.move_line_id and self.move_line_id.location_dest_id:
            self.write({'location_id': self.move_line_id.location_dest_id.id})

    def _update_location_from_move_line(self, move_line):
        """Enhanced location update from move line with comprehensive tracking"""
        _logger.warning('\n\n_update_location_from_move_line 1')
        self.ensure_one()
        if not move_line:
            return
            
        new_location = False
        location_changed = False
        
        # Determine the appropriate location based on move line state and type
        if move_line.qty_done and move_line.state == 'done':
            # Move is completed - use destination location
            _logger.warning('move_line.location_dest_id 1')
            new_location = move_line.location_dest_id
        else:
            return
            # Use source location for other cases
            _logger.warning('move_line.location_dest_id 2')
            new_location = move_line.location_id
            
        # Update location if it has changed
        if new_location and new_location != self.location_id:
            old_location = self.location_id
            self.write({'location_id': new_location.id})
            location_changed = True
            
            # Log the location change for traceability
            if old_location:
                self.message_post(
                    body=_('Location changed from %s to %s') %
                    (old_location.name, new_location.name)
                )
            else:
                self.message_post(
                    body=_('Location set to %s') %
                    (new_location.name)
                )
                
        return location_changed

    def _update_location_from_stock_move(self, stock_move, button_done=False):
        """Update location based on stock move information"""
        self.ensure_one()
        if not stock_move:
            return False
            
        new_location = False
        location_changed = False
        
        # Determine location based on move state and type
        if stock_move.state == 'done' or button_done:
            # Move is completed - use final destination
            new_location = stock_move.location_dest_id
        else:
            return
            # Move is draft - use source location
            new_location = stock_move.location_id
            
        # Update location if it has changed
        if new_location and new_location != self.location_id:
            old_location = self.location_id
            self.write({'location_id': new_location.id})
            location_changed = True
            
            # Log the location change
            if old_location:
                self.message_post(
                    body=_('Location updated from %s to %s via stock move %s') % 
                    (old_location.name, new_location.name, stock_move.name)
                )
            else:
                self.message_post(
                    body=_('Location set to %s via stock move %s') % 
                    (new_location.name, stock_move.name)
                )
                
        return location_changed

    def _update_location_from_picking(self, picking):
        """Update location based on picking information"""
        self.ensure_one()

        if not picking:
            return False
            
        new_location = False
        location_changed = False
        
        # Determine location based on picking type and state
        if picking.state == 'done':
            if picking.picking_type_id.code == 'outgoing':
                # Customer delivery - location is customer (external)
                new_location = picking.partner_id.property_stock_customer
            elif picking.picking_type_id.code == 'incoming':
                # Customer return - location is stock location
                new_location = self.env.ref('stock.stock_location_stock')
            elif picking.picking_type_id.code == 'internal':
                # Internal transfer - use destination location from move lines
                for move_line in picking.move_line_ids:
                    if move_line.setsco_serial_ids and self in move_line.setsco_serial_ids:
                        if move_line.location_dest_id:
                            new_location = move_line.location_dest_id
                            break
        elif picking.state in ['assigned', 'partially_available']:
            # Picking is assigned - use destination location
            for move_line in picking.move_line_ids:
                if move_line.setsco_serial_ids and self in move_line.setsco_serial_ids:
                    if move_line.location_dest_id:
                        new_location = move_line.location_dest_id
                        break
                        
        # Update location if it has changed
        if new_location and new_location != self.location_id:
            old_location = self.location_id
            self.write({'location_id': new_location.id})
            location_changed = True
            
            # Log the location change
            if old_location:
                self.message_post(
                    body=_('Location updated from %s to %s via picking %s') % 
                    (old_location.name, new_location.name, picking.name)
                )
            else:
                self.message_post(
                    body=_('Location set to %s via picking %s') % 
                    (new_location.name, picking.name)
                )
        
        return location_changed

    def action_set_scrapped(self):
        """Set serial to scrapped state"""
        for rec in self:
            rec.write({
                'state': 'scrapped',
                'scrap_date': fields.Datetime.now()
            })

    def action_void_from_production(self):
        """Remove SETSCO from manufacturing production to allow reassignment"""
        if not self:
            return
        
        # Filter records that can be voided
        voidable_records = self
        
        if not voidable_records:
            if len(self) == 1:
                if  self.state not in ['manufacturing','new']:
                    raise UserError(_('Only SETSCO serial numbers in manufacturing state can be voided from production.'))
            else:
                raise UserError(_('No SETSCO serial numbers can be voided. Only serial numbers in manufacturing state with assigned production orders can be voided.'))
        
        voided_count = 0
        production_messages = {}
        
        for record in voidable_records:
            production = record.production_id
            
            # Remove the SETSCO from the production
            record.write({
                'production_id': False,
                'product_id': False,
                'state': 'new',  # Reset to new state so it can be reassigned
                'manufacturing_date': False,
                'lot_id': False,
                
            })
            
            # Log the action
            record.message_post(
                body=_('SETSCO serial number voided from manufacturing order %s. Available for reassignment.') % 
                production.name
            )
            
            # Collect production messages for batch posting
            if production.id not in production_messages:
                production_messages[production.id] = {
                    'production': production,
                    'serials': []
                }
            production_messages[production.id]['serials'].append(record.name)
            
            voided_count += 1
        
        # Post messages to productions
        for prod_data in production_messages.values():
            production = prod_data['production']
            serials = prod_data['serials']
            if len(serials) == 1:
                message = _('SETSCO serial number %s has been voided from this manufacturing order.') % serials[0]
            else:
                message = _('SETSCO serial numbers %s have been voided from this manufacturing order.') % ', '.join(serials)
            production.message_post(body=message)
        
        # Return notification
        if voided_count == 1:
            message = _('1 SETSCO serial number has been voided from its manufacturing order and is now available for reassignment.')
        else:
            message = _('%d SETSCO serial numbers have been voided from their manufacturing orders and are now available for reassignment.') % voided_count
        
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Success'),
        #         'message': message,
        #         'type': 'success',
        #         'sticky': False,
        #     }
        # }

    def action_view_setsco_serials(self):
        """View stock move line for this setsco serial number"""
        self.ensure_one()
        if not self.move_line_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No stock move line associated with this serial number.'),
                    'type': 'warning',
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Move Line'),
            'res_model': 'stock.move.line',
            'view_mode': 'form',
            'res_id': self.move_line_id.id,
            'context': {'create': False}
        }

    @api.model_create_multi
    def create_serial_range(self, start_serial, end_serial, category_id=None, product_id=None, **kwargs):
        """Create a range of serial numbers"""
        import re
        
        # Extract prefix and numeric parts
        start_match = re.match(r'([A-Za-z]+)(\d+)', start_serial)
        end_match = re.match(r'([A-Za-z]+)(\d+)', end_serial)
        
        if not start_match or not end_match:
            raise ValidationError(_('Serial numbers must follow format like AS00001'))
        
        start_prefix, start_num_str = start_match.groups()
        end_prefix, end_num_str = end_match.groups()
        
        if start_prefix != end_prefix:
            raise ValidationError(_('Start and end serial numbers must have the same prefix'))
        
        start_num = int(start_num_str)
        end_num = int(end_num_str)
        num_length = len(start_num_str)
        
        if start_num > end_num:
            raise ValidationError(_('Start number must be less than or equal to end number'))
        
        # Validate category_id is provided
        if not category_id:
            raise ValidationError(_('Product category is required for creating serial numbers'))
        
        created_serials = []
        for num in range(start_num, end_num + 1):
            serial_name = f"{start_prefix}{num:0{num_length}d}"
            
            # Check if serial already exists in the same category
            existing = self.search([
                ('name', '=', serial_name),
                ('category_id', '=', category_id)
            ])
            if existing:
                continue  # Skip existing serials
            
            vals = {
                'name': serial_name,
                'category_id': category_id,
                'product_id': product_id,
                'state': kwargs.get('state', 'new'),
            }
            vals.update(kwargs)
            
            serial = self.create(vals)
            created_serials.append(serial)
        
        return created_serials

    def action_assign_product(self):
        """Open wizard to assign product to serial number"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Product'),
            'res_model': 'setsco.serial.product.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_setsco_serial_id': self.id,
            }
        }

    def action_open_migration_serial_range_wizard(self):
        """Open migration serial range wizard (create range with product and location)."""
        ctx = dict(self.env.context)
        if len(self) == 1:
            if self.product_id:
                ctx['default_product_id'] = self.product_id.id
            if self.location_id:
                ctx['default_location_id'] = self.location_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Serial Range (Migration)'),
            'res_model': 'setsco.serial.range.migration.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def name_get(self):
        result = []
        for record in self:
            if record.product_id:
                name = f"{record.name} - {record.category_id.name} ({record.product_id.name})"
            else:
                name = f"{record.name} - {record.category_id.name}"
            result.append((record.id, name))
        return result 

    def action_print_setsco_tuv_report(self):
        # Example: implement logic to print report with title switch
        return self.env.ref('setsco_serial_number.action_report_setsco_tuv').report_action(self, data={'title': 'Setsco' if self.env.context.get('is_setsco') else 'TUV'}) 

    def _auto_update_location(self):
        """Automatically update location based on current state and operations"""
        self.ensure_one()
        location_updated = False
        
        # Update location based on current state and operations
        if self.state == 'new':
            # New serials - check if they have a purchase order
            if self.purchase_order_id and self.purchase_order_id.picking_ids:
                # Use the first receipt location
                receipt = self.purchase_order_id.picking_ids.filtered(lambda p: p.picking_type_id.code == 'incoming')[0]
                if receipt and receipt.location_dest_id:
                    location_updated = self._update_location_safely(receipt.location_dest_id, 'purchase receipt')
                    
        elif self.state == 'manufacturing':
            # Manufacturing - use production location
            if self.production_id and self.production_id.location_src_id:
                location_updated = self._update_location_safely(self.production_id.location_src_id, 'production')
                
        elif self.state == 'warehouse':
            # Warehouse - check current stock move line
            if self.move_line_id:
                location_updated = self._update_location_from_move_line(self.move_line_id)
            elif self.production_id and self.production_id.location_dest_id:
                # Use production destination location
                location_updated = self._update_location_safely(self.production_id.location_dest_id, 'production completion')
                
        elif self.state == 'delivered':
            # Delivered - check delivery picking
            if self.picking_id and self.picking_id.partner_id:
                # Use customer location
                customer_location = self.picking_id.partner_id.property_stock_customer
                if customer_location:
                    location_updated = self._update_location_safely(customer_location, 'customer delivery')
                    
        elif self.state == 'scrapped':
            # Scrapped - use scrap location
            scrap_location = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False)
            if scrap_location:
                location_updated = self._update_location_safely(scrap_location, 'scrap')
                
        return location_updated

    def _update_location_safely(self, new_location, reason):
        """Safely update location with logging"""
        if not new_location or new_location == self.location_id:
            return False
            
        old_location = self.location_id
        self.write({'location_id': new_location.id})
        
        # Log the location change
        if old_location:
            self.message_post(
                body=_('Location automatically updated from %s to %s (%s)') % 
                (old_location.name, new_location.name, reason)
            )
        else:
            self.message_post(
                body=_('Location automatically set to %s (%s)') % 
                (new_location.name, reason)
            )
            
        return True

    @api.model
    def _batch_update_locations(self, domain=None):
        """Batch update locations for multiple serial numbers"""
        if domain is None:
            domain = []
            
        serials = self.search(domain)
        updated_count = 0
        
        for serial in serials:
            try:
                if serial._auto_update_location():
                    updated_count += 1
            except Exception as e:
                _logger.error(f'Failed to update location for serial {serial.name}: {str(e)}')
                
        return updated_count 

    def assign_setsco_to_internal_company(self):
        """Open wizard to assign selected serials to an internal company."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign to Internal Company'),
            'res_model': 'setsco.internal.company.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_ids': self.ids,
            }
        }

    def receive_setsco_from_internal_company(self):
        """Open wizard to receive selected serials from an internal company."""
   
        category_ids = self.mapped('setsco_category_id').ids

        if len(category_ids) > 1:
            raise UserError(_("You can only receive from one Setsco Category at a time."))

        category_id = category_ids[0] if category_ids else False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Receive from Internal Company'),
            'res_model': 'setsco.internal.company.receive.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_ids': self.ids,
                'default_setsco_category_id': category_id,
            }
        }