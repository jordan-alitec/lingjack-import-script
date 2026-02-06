from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import re
import logging
_logger = logging.getLogger(__name__)


class SetscoSerialSelectionWizard(models.TransientModel):
    _name = 'setsco.serial.selection.wizard'
    _description = 'Setsco Serial Selection Wizard'
    _inherit = ['barcodes.barcode_events_mixin']

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        readonly=True
    )
    move_line_id = fields.Many2one(
        'stock.move.line',
        string='Move Line',
        readonly=True
    )
    move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        readonly=True
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        readonly=True
    )
    is_return = fields.Boolean(
        string='Is Return',
        default=False,
        help='True if this wizard is for a return receipt (incoming picking)'
    )
    quantity = fields.Integer(
        string='Required Quantity',
        default=1,
        required=True
    )
    use_range = fields.Boolean(string="Use Range", default=True)
    selection_mode = fields.Selection([
        ('individual', 'Individual Selection'),
        ('range', 'Range Selection'),
    ], string='Selection Mode', default='individual', required=True)
    
    # Individual selection
    selection_line_ids = fields.One2many(
        'setsco.serial.selection.wizard.line',
        'wizard_id',
        string='Serial Selection Lines'
    )
    
    # Range selection
    start_serial_id = fields.Many2one(
        'setsco.serial.number',
        string='Start Serial',
        domain="start_end_serial_domain"
    )
    end_serial_id = fields.Many2one(
        'setsco.serial.number',
        string='End Serial',
        domain="start_end_serial_domain"
    )
    
    preview_serial_ids = fields.Many2many(
        'setsco.serial.number',
        'wizard_preview_rel',
        string='Preview Serials',
    )
    
    preview_count = fields.Integer(
        string='Preview Count',
        compute='_compute_preview_count'
    )
    
    excluded_serial_ids = fields.Char(
        string='Excluded Serial IDs',
        compute='_compute_excluded_serial_ids',
        help='Comma-separated list of serial IDs already in selection list'
    )
    
    serial_domain = fields.Char(
        string='Serial Domain',
        compute='_compute_serial_domain',
        help='Dynamic domain for serial selection fields'
    )
    
    start_end_serial_domain = fields.Char(
        string='Start/End Serial Domain',
        compute='_compute_start_end_serial_domain',
        help='Dynamic domain for start_serial_id and end_serial_id fields'
    )
    
    quantity_warning = fields.Text(
        string='Quantity Warning',
        compute='_compute_quantity_warning',
        help='Warning message when selected quantity exceeds move quantity'
    )

    # Enhanced scanning fields
    individual_scan_input = fields.Char(
        string="Scan Individual Serial",
        help="Scan or enter individual serial numbers"
    )
    range_start_scan_input = fields.Char(
        string="Scan Range Start",
        help="Scan or enter the start serial number for range"
    )
    range_end_scan_input = fields.Char(
        string="Scan Range End", 
        help="Scan or enter the end serial number for range"
    )
    
    # Legacy fields for backward compatibility
    start_serial_scan = fields.Char(string="Scan Start Serial")
    end_serial_scan = fields.Char(string="Scan End Serial")
    start_serial_scan_input = fields.Char(string="Start Serial Input", help="Enter or scan the start serial number")
    end_serial_scan_input = fields.Char(string="End Serial Input", help="Enter or scan the end serial number")


    @api.depends('selection_line_ids')
    def _compute_preview_count(self):
        for wizard in self:
            wizard.preview_count = len(wizard.selection_line_ids)

    @api.depends('selection_line_ids')
    def _compute_excluded_serial_ids(self):
        """Compute excluded serial IDs for domain filtering"""
        for wizard in self:
            excluded_ids = []
            if wizard.selection_line_ids:
                excluded_ids = wizard.selection_line_ids.mapped('setsco_serial_id.id')
                excluded_ids = [str(sid) for sid in excluded_ids if sid]  # Convert to strings and filter out False/None
            wizard.excluded_serial_ids = ','.join(excluded_ids) if excluded_ids else '0'

    @api.depends('selection_line_ids', 'product_id', 'is_return')
    def _compute_serial_domain(self):
        """Compute dynamic domain for serial selection fields"""
        for wizard in self:
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if wizard.is_return else 'warehouse'
            
            domain_parts = [
                "('product_id', '=', product_id)",
                f"('state', '=', '{target_state}')",
                "('production_id', '!=', False)"
            ]
            
            # Add exclusion of already selected serials
            if wizard.selection_line_ids:
                selected_serial_ids = wizard.selection_line_ids.mapped('setsco_serial_id.id')
                selected_serial_ids = [sid for sid in selected_serial_ids if sid]
                if selected_serial_ids:
                    ids_str = ','.join(map(str, selected_serial_ids))
                    domain_parts.append(f"('id', 'not in', [{ids_str}])")
            
            wizard.serial_domain = f"[{', '.join(domain_parts)}]"
    
    @api.depends('is_return', 'product_id', 'move_id', 'picking_id')
    def _compute_start_end_serial_domain(self):
        """Compute dynamic domain for start_serial_id and end_serial_id fields"""
        for wizard in self:
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if wizard.is_return else 'warehouse'

            # Build domain list
            # - Only allow serials that are not tied to an active transfer
            # - Only show serials with a warehouse/location already set
            # - For outgoing/internal, restrict to the picking source warehouse/location
            domain = [
                '|',
                # ('move_line_id', '=', False),
                # ('move_line_id.state', 'in', ('done', 'cancel')),
                ('product_id', '=', wizard.product_id.id if wizard.product_id else False),
                ('state', '=', target_state),
            ]

            # For outgoing/internal (non-return), restrict to the source location/warehouse
            # so the user only sees serials available in that warehouse.
            if not wizard.is_return:
                source_location = wizard._get_source_location()
                if source_location:
                    domain.append(('location_id', 'child_of', source_location.id))
            
            # For returns, add filter for serials from original delivery order
            if wizard.is_return:
                original_serial_ids = wizard._get_original_delivery_serial_ids()
                if original_serial_ids:
                    domain.append(('id', 'in', original_serial_ids))
            
            # Convert domain list to string format for Char field
            wizard.start_end_serial_domain = str(domain)
    
    def _get_original_delivery_serial_ids(self):
        """Get serial IDs from the original delivery order for returns"""
        if not self.is_return:
            return []
        
        # Get the picking from move_id or picking_id
        picking = False
        if self.move_id and self.move_id.picking_id:
            picking = self.move_id.picking_id
        elif self.picking_id:
            picking = self.picking_id
        
        if not picking or not picking.return_id:
            return []
        
        # Get the original delivery order
        original_picking = picking.return_id
        if not original_picking or original_picking.picking_type_id.code != 'outgoing':
            return []

        History = self.env['setsco.serial.move.line.history']

        # Candidates = serials shipped on this DO (history), still delivered,
        # and whose latest outgoing delivery is THIS original_picking.
        shipped_hist = History.search([
            ('picking_id', '=', original_picking.id),
            ('picking_type_code', '=', 'outgoing'),
            ('event', '=', 'done'),
            ('setsco_serial_id.product_id', '=', self.product_id.id),
            ('setsco_serial_id.state', '=', 'delivered'),
        ])
        candidates = shipped_hist.mapped('setsco_serial_id')
        if not candidates:
            # Fallback for legacy data (before history existed / before backfill ran)
            legacy = self.env['setsco.serial.number'].search([
                '|', '|',
                ('delivery_picking_id', '=', original_picking.id),
                ('delivery_move_line_id.picking_id', '=', original_picking.id),
                ('move_line_id.picking_id', '=', original_picking.id),
                ('product_id', '=', self.product_id.id),
                ('state', '=', 'delivered'),
            ])
            return legacy.ids

        last_outgoing_hist = History.search([
            ('setsco_serial_id', 'in', candidates.ids),
            ('picking_type_code', '=', 'outgoing'),
            ('event', '=', 'done'),
        ], order='date desc, id desc')

        latest_by_serial = {}
        for h in last_outgoing_hist:
            sid = h.setsco_serial_id.id
            if sid not in latest_by_serial:
                latest_by_serial[sid] = h.picking_id.id

        valid_ids = [
            sid for sid in candidates.ids
            if latest_by_serial.get(sid) == original_picking.id
        ]
        return valid_ids

    @api.depends('selection_line_ids', 'product_id')
    def _compute_quantity_warning(self):
        for wizard in self:
            wizard.quantity_warning = ''
            if wizard.selection_line_ids and wizard.product_id:
                assigned_serials = wizard.selection_line_ids.mapped('setsco_serial_id').filtered(lambda s: s)
                if assigned_serials:
                    target_move = wizard._get_target_move()
                    if target_move and target_move.product_uom_qty:
                        move_quantity = target_move.product_uom_qty
                        selected_count = len(assigned_serials)
                        
                        if selected_count > move_quantity:
                            excess_count = selected_count - move_quantity
                            warning_message = _(
                                "You selected %(selected)d serials but the move quantity is only %(move_qty)d. "
                                "Only the first %(move_qty)d serials will be applied when you confirm. "
                                "%(excess)d serials will be ignored."
                            ) % {
                                'selected': selected_count,
                                'move_qty': int(move_quantity),
                                'excess': excess_count
                            }
                            wizard.quantity_warning = warning_message

    # @api.onchange('product_id', 'quantity')
    # def _onchange_product_quantity(self):
    #     """Update individual lines when product or quantity changes"""
    #     if self.selection_mode == 'individual' and self.product_id:
    #         self._populate_individual_lines()

    @api.onchange('selection_line_ids')
    def _onchange_selection_lines(self):
        """Keep preview in sync with current selected/assigned lines and update domain"""
        assigned_serials = self.selection_line_ids.mapped('setsco_serial_id').filtered(lambda s: s)
        # self.preview_serial_ids = [(6, 0, assigned_serials.ids)]
        
        # Clear start_serial_id and end_serial_id if they are already in the selection list
        if self.start_serial_id and self.start_serial_id in assigned_serials:
            self.start_serial_id = False
        if self.end_serial_id and self.end_serial_id in assigned_serials:
            self.end_serial_id = False



    def _get_target_state(self):
        """Get the target state for serial filtering based on return status"""
        return 'delivered' if self.is_return else 'warehouse'
    
    def _get_source_location(self):
        """Get the source location for the transfer"""
        if self.move_id:
            return self.move_id.location_id
        elif self.picking_id:
            return self.picking_id.location_id
        return False

    def _get_target_move(self):
        """Get the target move for this wizard"""
        if self.move_id:
            return self.move_id
        elif self.picking_id and self.picking_id.move_ids:
            # Use first move that matches product if available
            candidate = self.picking_id.move_ids.filtered(lambda m: m.product_id == self.product_id)
            target_move = (candidate[:1] or self.picking_id.move_ids[:1])
            return target_move and target_move[0]
        return False

    def _populate_individual_lines(self):
        """Populate individual selection lines based on quantity"""
        # Clear existing lines
        self.selection_line_ids = [(5, 0, 0)]
        
        # Create new lines
        lines = []
        for i in range(self.quantity):
            lines.append((0, 0, {
                'sequence': i + 1,
                'product_id': self.product_id.id,
            }))
        
        self.selection_line_ids = lines

    def _update_range_preview(self):
        """Update the range preview based on start and end serials"""
        if not self.start_serial_id or not self.end_serial_id:
            self.preview_serial_ids = [(6, 0, [])]
            return
            
        # Get all serials between start and end
        serials = self._get_serials_in_range(self.start_serial_id.name, self.end_serial_id.name)
        self.preview_serial_ids = [(6, 0, serials.ids)]

    def _get_serials_in_range_prefix(self, start_name, end_name):
        """Get all serials between start and end names"""
        # Extract prefix and number parts
        start_match = re.match(r'([A-Za-z]+)(\d+)', start_name)
        end_match = re.match(r'([A-Za-z]+)(\d+)', end_name)
        
        if not start_match or not end_match:
            raise UserError(_('Invalid serial number format. Expected format: LETTERS + NUMBERS (e.g., AB00001)'))
        
        start_prefix, start_num = start_match.groups()
        end_prefix, end_num = end_match.groups()
        
        if start_prefix != end_prefix:
            raise UserError(_('Start and end serials must have the same prefix'))
        
        try:
            start_int = int(start_num)
            end_int = int(end_num)
        except ValueError:
            raise UserError(_('Invalid number format in serial numbers'))
        
        if start_int > end_int:
            start_int, end_int = end_int, start_int
        
        width = len(start_num)
        serial_names = [f"{start_prefix}{i:0{width}d}" for i in range(start_int, end_int + 1)]

        return serial_names
        
    def _get_serials_in_range(self, start_name, end_name):
        """Get all serials between start and end names"""
        # Extract prefix and number parts
        start_match = re.match(r'([A-Za-z]+)(\d+)', start_name)
        end_match = re.match(r'([A-Za-z]+)(\d+)', end_name)
        
        if not start_match or not end_match:
            raise UserError(_('Invalid serial number format. Expected format: LETTERS + NUMBERS (e.g., AB00001)'))
        
        start_prefix, start_num = start_match.groups()
        end_prefix, end_num = end_match.groups()
        
        if start_prefix != end_prefix:
            raise UserError(_('Start and end serials must have the same prefix'))
        
        try:
            start_int = int(start_num)
            end_int = int(end_num)
        except ValueError:
            raise UserError(_('Invalid number format in serial numbers'))
        
        if start_int > end_int:
            start_int, end_int = end_int, start_int
        
        # Generate all serial names in range
        serial_names = [f"{start_prefix}{i:05d}" for i in range(start_int, end_int + 1)]
        
        # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
        target_state = 'delivered' if self.is_return else 'warehouse'
        
        # Strict domain (original)
        domain_strict = [
            ('name', 'in', serial_names),
            ('product_id', '=', self.product_id.id),
            ('state', '=', target_state),
            

        ]
        source_location = self._get_source_location()
        if source_location:
            domain_strict.append(('location_id', '=', source_location.id))
        
        Serial = self.env['setsco.serial.number']
        serials = Serial.search(domain_strict)
        if serials:
            return serials
        
        # Fallback 1: relax state/production/move_line filters
        domain_relaxed = [
            ('name', 'in', serial_names),
            ('product_id', '=', self.product_id.id),
        ]
        if source_location:
            domain_relaxed.append(('location_id', '=', source_location.id))
        serials = Serial.search(domain_relaxed)
        if serials:
            return serials
        
        # Fallback 2: drop product filter (any product)
        domain_any_product = [('name', 'in', serial_names)]
        if source_location:
            domain_any_product.append(('location_id', '=', source_location.id))
        serials = Serial.search(domain_any_product)
        return serials

    def action_scan_individual_serial(self):
        """Open camera QR scanner for individual serial"""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'individual_scan_input',
                'wizard_id': self.id,
                'scanner_mode': 'camera',
            }
        }


    def action_scan_range_start(self):
        """Open camera QR scanner for range start"""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'range_start_scan_input',
                'wizard_id': self.id,
                'scanner_mode': 'camera',
            }
        }

    def action_scan_range_end(self):
        """Open camera QR scanner for range end"""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'range_end_scan_input',
                'wizard_id': self.id,
                'scanner_mode': 'camera',
            }
        }



    def action_scan_range(self):
        """Open camera QR scanner for range scanning with single button flow (start then end)."""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'range',  # activates JS range mode (first= start, second=end)
                'wizard_id': self.id,
                'model': 'setsco.serial.selection.wizard',
                'scanner_mode': 'camera',
            }
        }


    @api.onchange('individual_scan_input')
    def _onchange_individual_scan_input(self):
        """Handle individual serial input from scanning or manual entry"""
        if self.individual_scan_input:
            # Find the serial by name
            serial = self._find_serial_by_name(self.individual_scan_input)
            if serial:
                # Add to individual selection lines
                self._add_serial_to_individual_list(serial)
                # Clear the input field
                self.individual_scan_input = ''
            else:
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for this product.') % self.individual_scan_input
                    }
                }

    @api.onchange('range_start_scan_input')
    def _onchange_range_start_scan_input(self):
        """Handle range start serial input"""
        if self.range_start_scan_input:
            serial = self._find_serial_by_name(self.range_start_scan_input)
            if serial:
                self.start_serial_id = serial
                # Auto-update preview if end is already set
                if self.end_serial_id:
                    self._update_range_preview()
                self.range_start_scan_input = ''
            else:
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Start serial number "%s" not found or not available for this product.') % self.range_start_scan_input
                    }
                }

    @api.onchange('range_end_scan_input')
    def _onchange_range_end_scan_input(self):
        """Handle range end serial input"""
        if self.range_end_scan_input:
            serial = self._find_serial_by_name(self.range_end_scan_input)
            if serial:
                self.end_serial_id = serial
                # Auto-update preview if start is already set
                if self.start_serial_id:
                    self._update_range_preview()
                self.range_end_scan_input = ''
            else:
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('End serial number "%s" not found or not available for this product.') % self.range_end_scan_input
                    }
                }

    def _find_serial_by_name(self, serial_name):
        """Find serial by name and, if needed, perform a warehouse-agnostic
        location swap between warehouses by only updating `location_id` on
        two `setsco.serial.number` records (no stock moves).

        Rules enforced:
        - If scanned serial (or counterpart) is linked to a move line whose
          state is not in ('done', 'cancel'), block selection.
        - If mirror sublocation does not exist in the other warehouse, block.
        - If no available counterpart in the picking warehouse, block.
        - Works for any warehouse pair by deriving stock roots from
          `stock.warehouse.lot_stock_id`.
        """
        if not serial_name:
            return False

        # Clean the serial name
        serial_name = serial_name.strip()

        match = re.search(r'\((.*?)\)', serial_name)
        if match:
            serial_name = match.group(1)
       
        Serial = self.env['setsco.serial.number']
        Location = self.env['stock.location']
        Warehouse = self.env['stock.warehouse']

        # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
        target_state = 'delivered' if self.is_return else 'warehouse'
   
        # 1) Find scanned serial without restricting by source location
        scanned = Serial.sudo().search([
            ('name', '=', str(serial_name)),
            ('product_id', '=', self.product_id.id),
            ('state', '=', target_state),
        ], limit=1)
   
        # asd = asd
        if not scanned:
            return False

        # Block if scanned serial linked to active move line
        if scanned.move_line_id and scanned.move_line_id.state not in ('done', 'cancel'):
            raise ValidationError(_(
                "Serial '%(serial)s' is currently assigned to a transfer (state: %(state)s)."
            ) % {
                'serial': scanned.name,
                'state': scanned.move_line_id.state,
            })

        # Helper: resolve warehouse for a location via parent_of relation
        def get_warehouse_for_location(loc):
            if not loc:
                return Warehouse
            return Warehouse.search([('view_location_id', 'parent_of', loc.id)], limit=1)

        # Helper: compute suffix of a location under a stock root
        def get_suffix(stock_root, loc):
            root_path = stock_root.complete_name
            loc_path = loc.complete_name
            if loc_path == root_path:
                return ''
            prefix = root_path + '/'
            if loc_path.startswith(prefix):
                return loc_path[len(prefix):]
            return False

        # Helper: find mirror location by suffix under a stock root
        def find_mirror_location(stock_root, suffix):
            if suffix == '':
                return stock_root
            target_full = stock_root.complete_name + '/' + suffix
            return Location.search([('complete_name', '=', target_full)], limit=1)

        source_location = self._get_source_location()
        if not source_location:
            # Without a source context, just return the scanned serial
            return scanned

        # For returns, skip warehouse swapping logic - just return the scanned serial
        # The location will be updated when the return is processed
        if self.is_return:
            return scanned

        picking_wh = get_warehouse_for_location(source_location)
        scanned_wh = get_warehouse_for_location(scanned.location_id)

   

        # If warehouses match, nothing to swap
        if picking_wh and scanned_wh and picking_wh.id == scanned_wh.id:
            return scanned

        if not picking_wh or not scanned_wh:
            raise ValidationError(_('Unable to determine warehouses for source or scanned serial locations.'))

        # Derive stock roots
        picking_stock_root = picking_wh.lot_stock_id
        scanned_stock_root = scanned_wh.lot_stock_id
        if not picking_stock_root or not scanned_stock_root:
            raise ValidationError(_('Warehouse stock roots are not properly configured.'))

        # Suffix of scanned serial under its own warehouse stock root
        scanned_suffix = get_suffix(scanned_stock_root, scanned.location_id)
        if scanned_suffix is False:
            raise ValidationError(_(
                "Location '%(loc)s' is not under the stock root '%(root)s'."
            ) % {'loc': scanned.location_id.complete_name, 'root': scanned_stock_root.complete_name})

        # Expected destination for scanned serial in the picking warehouse
        dest_in_picking_wh = find_mirror_location(picking_stock_root, scanned_suffix)
        if not dest_in_picking_wh:
            raise ValidationError(_(
                "Exact sublocation '%(suffix)s' does not exist under '%(root)s' in the picking warehouse."
            ) % {'suffix': scanned_suffix or '/', 'root': picking_stock_root.complete_name})

        # 4) Find counterpart serial inside the picking warehouse
        # Prefer counterpart with the same suffix first
        preferred_loc = dest_in_picking_wh
        # Exclude serials that are currently assigned to an active move line
        availability_domain = ['|', ('move_line_id', '=', False), ('move_line_id.state', 'in', ('done', 'cancel'))]

        # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
        target_state = 'delivered' if self.is_return else 'warehouse'
        
        counterpart_domain = [
            ('product_id', '=', self.product_id.id),
            ('state', '=', target_state),
            ('id', '!=', scanned.id),
            ('location_id', 'child_of', picking_stock_root.id),
        ] + availability_domain
        # First try exact same sublocation
        counterpart = Serial.search(counterpart_domain + [('location_id', '=', preferred_loc.id)], limit=1)
        if not counterpart:
            counterpart = Serial.search(counterpart_domain, limit=1)

        if not counterpart:
            raise ValidationError(_(
                "No available serial for product '%(product)s' in the picking warehouse to swap with."
            ) % {'product': self.product_id.display_name})

        # Block if counterpart is busy
        if counterpart.move_line_id and counterpart.move_line_id.state not in ('done', 'cancel'):
            raise ValidationError(_(
                "Counterpart serial '%(serial)s' is currently assigned to a transfer (state: %(state)s)."
            ) % {'serial': counterpart.name, 'state': counterpart.move_line_id.state})

        # Compute counterpart suffix within picking stock root
        counterpart_suffix = get_suffix(picking_stock_root, counterpart.location_id)
        if counterpart_suffix is False:
            raise ValidationError(_(
                "Counterpart location '%(loc)s' is not under the stock root '%(root)s'."
            ) % {'loc': counterpart.location_id.complete_name, 'root': picking_stock_root.complete_name})

        # Ensure mirror exists in scanned serial's warehouse for counterpart
        dest_for_counterpart_in_scanned_wh = find_mirror_location(scanned_stock_root, counterpart_suffix)
        if not dest_for_counterpart_in_scanned_wh:
            raise ValidationError(_(
                "Exact sublocation '%(suffix)s' does not exist under '%(root)s' in the scanned serial's warehouse."
            ) % {'suffix': counterpart_suffix or '/', 'root': scanned_stock_root.complete_name})

        # 6) Apply location swap (no stock moves)
        scanned.location_id = dest_in_picking_wh.id
        counterpart.location_id = dest_for_counterpart_in_scanned_wh.id

        # Informational log
        _logger.info(
            "Swapped locations between serials: %s -> %s, %s -> %s",
            scanned.name,
            dest_in_picking_wh.complete_name,
            counterpart.name,
            dest_for_counterpart_in_scanned_wh.complete_name,
        )

        # Return scanned serial (now in the picking warehouse)
        return scanned

    def _add_serial_to_individual_list(self, serial_name):
        """Add serial to individual selection list, preventing duplicates"""
        # Check if serial is already in the list
       
        serial = self._find_serial_by_name(serial_name)

        existing_line = self.selection_line_ids.filtered(lambda line: line.setsco_serial_id == serial)
        if existing_line:
            
            return {
                'warning': {
                    'title': _('Duplicate Serial'),
                    'message': _('Serial number "%s" is already in the list.') % serial.name
                }
            }
        
        # Always create a new line for better visibility
        new_sequence = max(self.selection_line_ids.mapped('sequence')) + 1 if self.selection_line_ids else 1
        
        # Create new line with the serial
        new_line_vals = {
            'sequence': new_sequence,
            'setsco_serial_id': serial.id,
            'product_id': self.product_id.id,
        }
        
        # Add the new line to the list
        self.selection_line_ids = [(0, 0, new_line_vals)]
        
        # Log for debugging
        _logger.warning(f"Added serial '{serial.name}' to wizard line list. Total lines: {len(self.selection_line_ids)}")
        
        return True

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = dict(self.env.context or {})
        # Resolve move from vals/context robustly (id or record)
        move = False
        move_val = vals.get('move_id') or ctx.get('default_move_id')
        if move_val:
            move = move_val if isinstance(move_val, self.env['stock.move'].__class__) else self.env[
                'stock.move'].browse(move_val)
        elif ctx.get('active_model') == 'stock.move' and ctx.get('active_id'):
            move = self.env['stock.move'].browse(ctx['active_id'])
        # elif ctx.get('active_model') == 'stock.move.line' and ctx.get('active_id'):
        #     # Fallback: derive move from move_line
        #     move_line = self.env['stock.move.line'].browse(ctx['active_id'])
        #     if move_line.exists():
        #         move = move_line.move_id
        
        # Detect if this is a return picking
        is_return = False
        picking = False
        
        # Check from move
        if move and move.exists():
            picking = move.picking_id
        
        # Check from move_line_id
        if not picking:
            move_line_val = vals.get('move_line_id') or ctx.get('default_move_line_id')
            if move_line_val:
                move_line = move_line_val if isinstance(move_line_val, self.env['stock.move.line'].__class__) else self.env['stock.move.line'].browse(move_line_val)
                if move_line.exists():
                    picking = move_line.picking_id
        
        # Check from picking_id
        if not picking:
            picking_val = vals.get('picking_id') or ctx.get('default_picking_id')
            if picking_val:
                picking = picking_val if isinstance(picking_val, self.env['stock.picking'].__class__) else self.env['stock.picking'].browse(picking_val)
        
        # Determine if it's a return
        if picking and picking.exists():
            if picking.picking_type_id.code == 'incoming' and picking.return_id:
                is_return = True
        elif ctx.get('default_is_return'):
            is_return = ctx.get('default_is_return')
        
        if 'is_return' in self._fields and 'is_return' not in vals:
            vals['is_return'] = is_return
        
        if move and move.exists():
            # Default product/quantity if applicable
            if 'product_id' in self._fields and not vals.get('product_id') and move.product_id:
                vals['product_id'] = move.product_id.id
            if 'quantity' in self._fields and vals.get('quantity') is None:
                # Count assigned serials across all move lines
                assigned_cnt = sum(len(ml.setsco_serial_ids) for ml in move.move_line_ids)
                vals['quantity'] = assigned_cnt

            # Prefill lines from all move_lines’ assigned setsco_serial_ids
            lines_cmds = []
            preview_ids = []
            seq = 1
            for ml in move.move_line_ids:
                for s in ml.setsco_serial_ids:
                    lines_cmds.append((0, 0, {
                        'sequence': seq,
                        'setsco_serial_id': s.id,
                        'product_id': ml.product_id.id,
                        # 'move_line_id': ml.id,
                    }))
                    preview_ids.append(s.id)
                    seq += 1

            if lines_cmds:
                vals['selection_line_ids'] = lines_cmds
                vals['preview_serial_ids'] = [(6, 0, preview_ids)]

        return vals

    def action_add_manual_serial(self):
        """Add manually selected serial to individual list"""
        if not self.start_serial_id:
            raise UserError(_('Please select a serial number first'))
        
        if self.selection_mode != 'individual':
            raise UserError(_('This action is only available in individual selection mode'))
        
        # Add the serial to the list
        self._add_serial_to_individual_list(self.start_serial_id.name)
        
        # Clear the field for next selection
        self.start_serial_id = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Serial added to selection list'),
                'type': 'success',
            }
        }

    def action_add_range_manual(self):
        """Add manually selected range to individual list"""
        if not self.start_serial_id or not self.end_serial_id:
            raise UserError(_('Please select both start and end serial numbers'))
        
        if self.selection_mode != 'range':
            raise UserError(_('This action is only available in range selection mode'))
        
        # Add the range to the list
        self.action_add_range_to_list()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Range added to selection list'),
                'type': 'success',
            }
        }

    def action_add_range_to_list(self):
        """Add current range to individual selection list"""
        if not self.start_serial_id or not self.end_serial_id:
            raise UserError(_('Please select both start and end serial numbers'))
       
        serials = self._get_serials_in_range_prefix(self.start_serial_id.name, self.end_serial_id.name)
       
     
        # Add each serial to individual list
        for serial in serials:
            try:
                self._add_serial_to_individual_list(serial)
            except Exception:
                continue

        # Clear range selection
        self.start_serial_id = False
        self.end_serial_id = False
        # self.preview_serial_ids = [(6, 0, [])]

    def action_clear_all(self):
        """Clear all selected serials"""
        self.selection_line_ids = [(5, 0, 0)]
        self.preview_serial_ids = [(6, 0, [])]
        self.start_serial_id = False
        self.end_serial_id = False
        self.individual_scan_input = ''
        self.range_start_scan_input = ''
        self.range_end_scan_input = ''

        self.action_confirm_selection()

        return {
            'name': "Select Setsco Serial Range",
            'type': "ir.actions.act_window",
            'res_model': "setsco.serial.selection.wizard",
            'view_mode': "form",
            'views': [[False, "form"]],
            'target': "new",
            'context': {
                'default_move_id': self.move_id.id,
                'default_move_line_id': self.move_line_id.id,
                'default_product_id': self.product_id.id,
                'default_quantity': 0,
            },
        }

    def action_remove_serial_line(self):
        """Remove this specific serial line (called from button in list view)"""
        # This method is called from the button in the list view
        # The context will contain the active_id which is the line record
        active_id = self.env.context.get('active_id')
        if active_id:
            line = self.env['setsco.serial.selection.wizard.line'].browse(active_id)
            if line.exists() and line.wizard_id == self:
                serial = line.setsco_serial_id
       
                line.unlink()

                # If serial is presently assigned to this wizard's move line, clear it
                if serial and self.move_line_id and serial.move_line_id == self.move_line_id:
                    serial.move_line_id = False
        return False

    def action_confirm_selection(self):
            """Confirm the selection by rebuilding move lines from current wizard lines.
            - Remove all existing stock.move.line(s) for this product in the target move
            - Create new move lines: one per selected serial (set lot, quantity, qty_done)
            - Link each serial to its new move line (setsco_serial_ids)
            - Align move demanded quantity (product_uom_qty) with selected count
            """
        # try:

            # Resolve target move and locations
            target_move = self._get_target_move()
            if not target_move:
                raise UserError(_("No target move found to rebuild move lines."))

            product = self.product_id or (target_move and target_move.product_id)
            if not product:
                raise UserError(_("Product is required to rebuild move lines."))


            if not self.selection_line_ids:
                existing_mls = target_move.move_line_ids.filtered(lambda ml: ml.product_id == product)
                if existing_mls:
                   
                    existing_mls.unlink()
                target_move.picking_id.action_assign()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': "Successfully cleared the setsco serial numbers",
                        'type': 'success',
                        'next': {'type': 'ir.actions.client','tag': 'reload',},
                    }
                }

            # Collect selected serials
            selected_serials = self.selection_line_ids.mapped('setsco_serial_id').filtered(lambda s: s)
            if not selected_serials:
                raise UserError(_("No valid serials found in the selection."))

            # Apply quantity limit if needed (user was already warned via onchange)
            move_quantity = target_move.product_uom_qty
            selected_count = len(selected_serials)

            if selected_count > move_quantity:
                # Limit to move quantity (user was already warned)
                final_serials = selected_serials[:int(move_quantity)]
            else:
                final_serials = selected_serials

            src_loc = target_move.location_id
            dst_loc = target_move.location_dest_id
            uom = target_move.product_uom

            # Remove existing move lines for this product in the move
            existing_mls = target_move.move_line_ids.filtered(lambda ml: ml.product_id == product)

         
            if existing_mls:
                existing_mls.unlink()
       
            # Keep move's original product_uom_qty (don't override it)
            # The move quantity should remain as originally set

            MoveLine = self.env['stock.move.line']
            new_mls = self.env['stock.move.line']
   
            # Create new move lines, one per serial
            for serial in final_serials:
                ml_vals = {
                    'move_id': target_move.id,
                    'product_id': product.id,
                    'product_uom_id': uom.id if uom else product.uom_id.id,
                    'location_id': src_loc.id if src_loc else False,
                    'location_dest_id': dst_loc.id if dst_loc else False,
                    'quantity': 1,  # planned per-line quantity
                    'qty_done': 1,  # done per-line quantity
                    'picked': True,
                    'picking_id': target_move.picking_id.id,  # done per-line quantity
                    'lot_id': serial.lot_id.id if getattr(serial, 'lot_id', False) else False,
                    # Link serial by inverse One2many
                    'setsco_serial_ids': [(6, 0, [serial.id])],
                }
                new_ml = MoveLine.create(ml_vals)
                # Update serial's move_line_id so button_validate can find it
                # Note: Don't change state here - state will be changed when picking is validated
                serial.write({'move_line_id': new_ml.id})
                # new_ml.qty_done = 1
                new_mls |= new_ml
           
           
            success_message = _('Move lines rebuilt from %d selected serials') % len(final_serials)
            if selected_count > move_quantity:
                success_message += _(' (limited to move quantity)')
          
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': success_message,
                    'type': 'success',
                    'next': {'type': 'ir.actions.client','tag': 'reload',},
                }
            }

        # except Exception as e:
            # raise UserError(_("Failed to confirm selection: %s") % str(e))

    def add_individual_serial_from_scan(self, serial_number):
        """Add individual serial from QR scan"""
        try:
            # Clean the serial number
            serial_number = serial_number

            # Find the serial by name
            serial = self._find_serial_by_name(serial_number)
        
            if not serial:
                # Provide detailed error message with search criteria
                error_msg = f"Serial number '{serial_number}' not found.\n\n"
                error_msg += f"Product: {self.product_id.name}\n"
                error_msg += f"Search criteria: name='{serial_number}', product_id={self.product_id.id}\n"
                
                # Check if serial exists at all
                all_serials = self.env['setsco.serial.number'].search([('name', '=', serial_number)])
                if all_serials:
                    error_msg += f"\nSerial exists but doesn't match criteria:\n"
                    for s in all_serials:
                        error_msg += f"- Serial: {s.name}, Product: {s.product_id.name}, State: {s.state}, Production: {s.production_id.name if s.production_id else 'None'}, Move Line: {s.move_line_id.name if s.move_line_id else 'None'}\n"
                else:
                    error_msg += f"\nSerial '{serial_number}' does not exist in the system."
                
                raise UserError(_(error_msg))
            
            # Check if already in list
        
            existing = self.selection_line_ids.filtered(lambda line: line.setsco_serial_id == serial)

            if existing:
                return False
            
            # Add to selection list
            self._add_serial_to_individual_list(serial.name)
            
            # Log for debugging
            _logger.info(f"Added serial '{serial_number}' to wizard. Total lines: {len(self.selection_line_ids)}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Serial %s added to list') % serial_number,
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.warning(f"error: {e}")
            return False

    def set_range_start_serial_from_scan(self, serial_number):
        """Set range start serial from QR scan"""
        try:
            # Clean the serial number
            serial_number = serial_number.strip()
            
            # Find the serial by name
            serial = self._find_serial_by_name(serial_number)
            if not serial:
                # Provide detailed error message
                error_msg = f"Serial number '{serial_number}' not found.\n\n"
                error_msg += f"Product: {self.product_id.name}\n"
                error_msg += f"Search criteria: name='{serial_number}', product_id={self.product_id.id}\n"
                
                # Check if serial exists at all
                all_serials = self.env['setsco.serial.number'].search([('name', '=', serial_number)])
                if all_serials:
                    error_msg += f"\nSerial exists but doesn't match criteria:\n"
                    for s in all_serials:
                        error_msg += f"- Serial: {s.name}, Product: {s.product_id.name}, State: {s.state}, Production: {s.production_id.name if s.production_id else 'None'}, Move Line: {s.move_line_id.name if s.move_line_id else 'None'}\n"
                else:
                    error_msg += f"\nSerial '{serial_number}' does not exist in the system."
                
                raise UserError(_(error_msg))
            
            # Set as start serial
            self.start_serial_id = serial.id
            self.range_start_scan_input = serial_number
            
            # Update preview
            self._update_range_preview()
            
            # Log for debugging
            _logger.info(f"Set range start serial to '{serial_number}'")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Range start serial set to %s') % serial_number,
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_("Failed to set range start serial: %s") % str(e))

    def set_range_end_serial_from_scan(self, serial_number):
        """Set range end serial from QR scan"""
        try:
            # Clean the serial number
            serial_number = serial_number.strip()
            
            # Find the serial by name
            serial = self._find_serial_by_name(serial_number)
            if not serial:
                # Provide detailed error message
                error_msg = f"Serial number '{serial_number}' not found.\n\n"
                error_msg += f"Product: {self.product_id.name}\n"
                error_msg += f"Search criteria: name='{serial_number}', product_id={self.product_id.id}\n"
                
                # Check if serial exists at all
                all_serials = self.env['setsco.serial.number'].search([('name', '=', serial_number)])
                if all_serials:
                    error_msg += f"\nSerial exists but doesn't match criteria:\n"
                    for s in all_serials:
                        error_msg += f"- Serial: {s.name}, Product: {s.product_id.name}, State: {s.state}, Production: {s.production_id.name if s.production_id else 'None'}, Move Line: {s.move_line_id.name if s.move_line_id else 'None'}\n"
                else:
                    error_msg += f"\nSerial '{serial_number}' does not exist in the system."
                
                raise UserError(_(error_msg))
            
            # Set as end serial
            self.end_serial_id = serial.id
            self.range_end_scan_input = serial_number
            
            # Update preview
            self._update_range_preview()
            
            # Log for debugging
            _logger.info(f"Set range end serial to '{serial_number}'")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Range end serial set to %s') % serial_number,
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_("Failed to set range end serial: %s") % str(e))

    def _group_serials_by_lot(self, selected_serials=None):
        """Group selected serials by lot_id to create separate move lines for each lot"""
        if selected_serials is None:
            selected_serials = self.selection_line_ids.mapped('setsco_serial_id').filtered(lambda s: s)

        lot_groups = {}
        
        for serial in selected_serials:
            lot_id = serial.lot_id.id if serial.lot_id else False
            if lot_id not in lot_groups:
                lot_groups[lot_id] = []
            lot_groups[lot_id].append(serial)
            
        return lot_groups

    def _create_composite_lot(self, serials):
        """Create a composite lot for multiple serials without a single lot_id."""
        # This is a placeholder. In a real scenario, you might create a new lot record
        # or use a specific composite lot model.
        # For now, we'll just return a dummy lot or raise an error if not implemented.
        # A proper implementation would involve creating a new lot record.
        raise UserError(_("Composite lot creation is not fully implemented in this wizard."))

    def action_update_preview(self):
        """Manually update the range preview"""
        if self.selection_mode == 'range':
            self._update_range_preview()
        return {'type': 'ir.actions.do_nothing'}

    # Legacy methods for backward compatibility
    def action_scan_start_serial(self):
        """Open QR scanner for start serial"""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'start_serial_scan',
                'wizard_id': self.id,
            }
        }

    def action_scan_end_serial(self):
        """Open QR scanner for end serial"""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'end_serial_scan',
                'wizard_id': self.id,
            }
        }

    @api.onchange('start_serial_scan')
    def _onchange_start_serial_scan(self):
        if self.start_serial_scan:
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if self.is_return else 'warehouse'
            # Use the same domain as the field to include location filtering
            search_domain = [
                ('name', '=', self.start_serial_scan),
                ('product_id', '=', self.product_id.id),
                ('state', '=', target_state),
                
            ]
            
            # Add location filtering if source location is available
            source_location = self._get_source_location()
            if source_location:
                search_domain.append(('location_id', '=', source_location.id))
            
            serial = self.env['setsco.serial.number'].search(search_domain, limit=1)
            if serial:
                self.start_serial_id = serial
                # Trigger range preview update if both start and end are set
                if self.end_serial_id:
                    self._update_range_preview()
            else:
                self.start_serial_id = False

    @api.onchange('end_serial_scan')
    def _onchange_end_serial_scan(self):
        if self.end_serial_scan:
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if self.is_return else 'warehouse'
            serial = self.env['setsco.serial.number'].search([
                ('name', '=', self.end_serial_scan),
                ('product_id', '=', self.product_id.id),
                ('state', '=', target_state),
                
            ], limit=1)
            if serial:
                self.end_serial_id = serial
            else:
                self.end_serial_id = False

    @api.onchange('start_serial_id')
    def _onchange_start_serial_id(self):
        """Handle start serial selection - auto-add to individual list or prepare for range"""
        # Validate that the selected serial has the correct state
        if self.start_serial_id:
            target_state = self._get_target_state()
            if self.start_serial_id.state != target_state:
                self.start_serial_id = False
                return {
                    'warning': {
                        'title': _('Invalid Serial State'),
                        'message': _('Selected serial must be in "%s" state for this operation.') % target_state
                    }
                }
        
        if self.start_serial_id and self.selection_mode == 'individual':
            # For individual mode, automatically add the selected serial to the list
            self._add_serial_to_individual_list(self.start_serial_id.name)
            # Clear the field for next selection
            self.start_serial_id = False

    @api.onchange('end_serial_id')
    def _onchange_end_serial_id(self):
        """Handle end serial selection - auto-add range when both start and end are set"""
        # Validate that the selected serial has the correct state
        if self.end_serial_id:
            target_state = self._get_target_state()
            if self.end_serial_id.state != target_state:
                self.end_serial_id = False
                return {
                    'warning': {
                        'title': _('Invalid Serial State'),
                        'message': _('Selected serial must be in "%s" state for this operation.') % target_state
                    }
                }
        
        if self.end_serial_id and self.start_serial_id and self.selection_mode == 'range':
            # For range mode, automatically add the range when both are selected
            self.action_add_range_to_list()

    def _get_available_serials(self):
        """Get available serials excluding already selected ones"""
        # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
        target_state = 'delivered' if self.is_return else 'warehouse'
        domain = [
            ('product_id', '=', self.product_id.id),
            ('state', '=', target_state),
            ('production_id', '!=', False)
        ]
        
        # Exclude already selected serials
        if self.selection_line_ids:
            selected_serial_ids = self.selection_line_ids.mapped('setsco_serial_id.id')
            selected_serial_ids = [sid for sid in selected_serial_ids if sid]
            if selected_serial_ids:
                domain.append(('id', 'not in', selected_serial_ids))
        
        return self.env['setsco.serial.number'].search(domain)

    def action_get_available_serials(self):
        """Action to get available serials for the current wizard"""
        available_serials = self._get_available_serials()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Available Serial Numbers',
            'res_model': 'setsco.serial.number',
            'view_mode': 'list',
            'domain': [('id', 'in', available_serials.ids)],
            'target': 'new',
            'context': {
                'default_product_id': self.product_id.id,
                'wizard_id': self.id,
            }
        }

    def _update_serial_domains(self):
        """Update the domain for serial fields to exclude already selected ones"""
        # This method will be called from onchange to update the domain
        # The actual domain update will happen through the field definition
        pass

    def _filter_available_serials(self, serials):
        """Filter out serials that are already in the selection list"""
        if not self.selection_line_ids:
            return serials
        
        selected_serial_ids = self.selection_line_ids.mapped('setsco_serial_id.id')
        selected_serial_ids = [sid for sid in selected_serial_ids if sid]
        
        if not selected_serial_ids:
            return serials
        
        return serials.filtered(lambda s: s.id not in selected_serial_ids)

    @api.onchange('start_serial_scan_input')
    def _onchange_start_serial_scan_input(self):
        """Handle start serial input from scanning or manual entry"""
        if self.start_serial_scan_input:
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if self.is_return else 'warehouse'
            # Find the serial by name with proper domain
            serial = self.env['setsco.serial.number'].search([
                ('name', '=', self.start_serial_scan_input),
                ('product_id', '=', self.product_id.id),
                ('state', '=', target_state),
                
            ], limit=1)
            if serial:
                self.start_serial_id = serial
                self.start_serial_scan = self.start_serial_scan_input  # Also update the old field for compatibility
            else:
                self.start_serial_id = False
                # Show warning that serial not found
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for this product.') % self.start_serial_scan_input
                    }
                }

    @api.onchange('end_serial_scan_input')
    def _onchange_end_serial_scan_input(self):
        """Handle end serial input from scanning or manual entry"""
        if self.end_serial_scan_input:
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if self.is_return else 'warehouse'
            # Find the serial by name with proper domain
            serial = self.env['setsco.serial.number'].search([
                ('name', '=', self.end_serial_scan_input),
                ('product_id', '=', self.product_id.id),
                ('state', '=', target_state),
                

            ], limit=1)
            if serial:
                self.end_serial_id = serial
                self.end_serial_scan = self.end_serial_scan_input  # Also update the old field for compatibility
            else:
                self.end_serial_id = False
                # Show warning that serial not found
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for this product.') % self.end_serial_scan_input
                    }
                }


    @api.model_create_multi
    def create(self, vals_list):
        """Create wizard instances"""
        return super().create(vals_list)

    def on_barcode_scanned(self, barcode):
        """Handle barcode scanning through Odoo's barcode system"""
        self.ensure_one()
        
        # Extract SETSCO number from barcode content
        setsco_number = self._extract_setsco_number(barcode)
        
        if not setsco_number:
            return {
                'warning': {
                    'title': _('Invalid Barcode'),
                    'message': _('No valid SETSCO serial number found in barcode: %s') % barcode
                }
            }
        
        # Process based on selection mode
        if self.selection_mode == 'individual':
            return self._process_individual_barcode(setsco_number)
        elif self.selection_mode == 'range':
            return self._process_range_barcode(setsco_number)
        
        return {}

    def _extract_setsco_number(self, barcode_data):
        """Extract SETSCO number from barcode content"""
        if not barcode_data:
            return False
            
        # Clean the barcode data
        barcode_data = barcode_data.strip()
        
        # Pattern 1: SETSCO(value) - for complex format
        setsco_match = re.search(r'SETSCO\(([^)]+)\)', barcode_data)
        if setsco_match:
            return setsco_match.group(1)
        
        # Pattern 2: SETSCO\(value\) (escaped parentheses)
        setsco_match = re.search(r'SETSCO\\(([^)]+)\\)', barcode_data)
        if setsco_match:
            return setsco_match.group(1)
        
        # Pattern 3: SETSCO:value or SETSCO=value
        setsco_match = re.search(r'SETSCO[:=]([^\s,)]+)', barcode_data)
        if setsco_match:
            return setsco_match.group(1)
        
        # Pattern 4: Direct format - check if it looks like a SETSCO serial
        direct_match = re.search(r'^([A-Za-z]{2,3}\d{5,})$', barcode_data)
        if direct_match:
            return direct_match.group(1)
        
        # If no pattern matches, use the entire text as fallback
        return barcode_data if barcode_data else False

    def _process_individual_barcode(self, setsco_number):
        """Process individual serial barcode"""
        try:
            serial_name = setsco_number.strip()
            match = re.search(r'\((.*?)\)', serial_name)
            if match:
                serial_name = match.group(1)
        
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if self.is_return else 'warehouse'
            # Find the serial
            serial = self.env['setsco.serial.number'].search([
                ('name', '=', serial_name),
                ('product_id', '=', self.product_id.id),
                ('state', '=', target_state),
            ], limit=1)
            
            if not serial:
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for this product.') % serial_name
                    }
                }
            
            # Add to individual selection
            self.start_serial_id = serial
            self.individual_scan_input = serial_name
            
            return {}
            
        except Exception as e:
            return {
                'warning': {
                    'title': _('Error'),
                    'message': _('Failed to process serial number: %s') % str(e)
                }
            }

    def _process_range_barcode(self, setsco_number):
        """Process range serial barcode"""
        try:
            serial_name = setsco_number.strip()
            match = re.search(r'\((.*?)\)', serial_name)
            if match:
                serial_name = match.group(1)
        
            # Use 'delivered' state for returns, 'warehouse' for outgoing/internal
            target_state = 'delivered' if self.is_return else 'warehouse'
            # Find the serial
            serial = self.env['setsco.serial.number'].search([
                ('name', '=', serial_name),
                ('product_id', '=', self.product_id.id),
                ('state', '=', target_state),
            ], limit=1)
            
            if not serial:
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for this product.') % serial_name
                    }
                }
            

     
            # Determine if this is start or end based on current state
            if not self.start_serial_id:
                # This is the start serial
                self.start_serial_id = serial
                self.start_serial_scan_input = serial_name
                return {}
            else:
                # This is the end serial
                self.end_serial_id = serial
                self.end_serial_scan_input = serial_name
                
                # Add the range to the list
                self.action_add_range_to_list()
                
                return {}
                
        except Exception as e:
            return {
                'warning': {
                    'title': _('Error'),
                    'message': _('Failed to process serial number: %s') % str(e)
                }
            }


class SetscoSerialSelectionWizardLine(models.TransientModel):
    _name = 'setsco.serial.selection.wizard.line'
    _description = 'Setsco Serial Selection Wizard Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'setsco.serial.selection.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=1)
    setsco_serial_id = fields.Many2one(
        'setsco.serial.number',
        string='Setsco Serial Number',
        domain="[('product_id', '=', product_id)]"
    )
    product_id = fields.Many2one('product.product', string='Product', related='wizard_id.product_id', store=True)
    
    # Related fields for display
    serial_name = fields.Char(string='Serial Number', related='setsco_serial_id.name', readonly=True)
    serial_state = fields.Selection(string='State', related='setsco_serial_id.state', readonly=True)
    location_id = fields.Many2one(string='Location', related='setsco_serial_id.location_id', readonly=True)

    def action_remove_serial_line(self):
        """Remove this specific serial line"""
        self.unlink()
        return {'type': 'ir.actions.do_nothing'}

    @api.model
    def default_get(self, fields_list):
        """Set default values for new wizard lines"""
        vals = super().default_get(fields_list)
        
        # Get the wizard from context
        wizard_id = self.env.context.get('default_wizard_id')
        if wizard_id:
            wizard = self.env['setsco.serial.selection.wizard'].browse(wizard_id)
            if wizard.exists() and wizard.product_id:
                vals['product_id'] = wizard.product_id.id
        
        return vals

    @api.onchange('setsco_serial_id','serial_name')
    def _check_duplicate_serial(self):
        """Ensure no duplicate serials in the same wizard and validate state"""

        for line in self:
            if not line.setsco_serial_id:
                continue
            
            # Validate that the selected serial has the correct state
            if line.wizard_id:
                target_state = line.wizard_id._get_target_state()
                if line.setsco_serial_id.state != target_state:
                    line.setsco_serial_id = False
                    return {
                        'warning': {
                            'title': _('Invalid Serial State'),
                            'message': _('Selected serial must be in "%s" state for this operation.') % target_state
                        }
                    }
            
            duplicates = line.wizard_id.selection_line_ids.filtered(
                lambda l: l.id != line.id and l.setsco_serial_id == line.setsco_serial_id
            )
            if len(duplicates) > 1:
                raise ValidationError(_(
                    "Serial number '%s' is already selected in another line."
                ) % line.setsco_serial_id.display_name)
            

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure product_id is set when creating new lines"""
        for vals in vals_list:
            if not vals.get('product_id') and vals.get('wizard_id'):
                wizard = self.env['setsco.serial.selection.wizard'].browse(vals['wizard_id'])
                if wizard.exists() and wizard.product_id:
                    vals['product_id'] = wizard.product_id.id

        return super().create(vals_list)