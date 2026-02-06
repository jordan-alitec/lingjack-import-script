from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SetscoSerialAssignmentWizard(models.TransientModel):
    _name = 'setsco.serial.assignment.wizard'
    _description = 'Setsco Serial Assignment Wizard'
    _transient_max_count = 100  # Keep more records
    _transient_max_hours = 24   # Keep for 24 hours instead of default 1 hour

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', required=True)

    is_rework = fields.Boolean(string='Is Modification', related="production_id.is_rework")
    
    product_id = fields.Many2one('product.product', string='Product', required=True)
    category_id = fields.Many2one('setsco.category', string='Product Category',
                                  related='product_id.setsco_category_id', readonly=True)
    quantity = fields.Float(string='Quantity', required=True,digits='Product Unit of Measure')
    
    # Range selection mode
    use_range_selection = fields.Boolean(string='Use Range Selection', default=False)
    start_serial_id = fields.Many2one('setsco.serial.number', string='Start Serial Number')
    end_serial_id = fields.Many2one('setsco.serial.number', string='End Serial Number')
    
    assignment_line_ids = fields.One2many('setsco.serial.assignment.wizard.line', 'wizard_id', 
                                           string='Serial Number Assignments')
    
    # Warning message for quantity limitation
    range_warning = fields.Text(string='Range Warning', compute='_compute_range_warning')

    start_serial_scan = fields.Char(string="Scan Start Serial")
    end_serial_scan = fields.Char(string="Scan End Serial")
    
    # New char fields for scanning
    start_serial_scan_input = fields.Char(string="Start Serial Input", help="Enter or scan the start serial number")
    end_serial_scan_input = fields.Char(string="End Serial Input", help="Enter or scan the end serial number")

    def _get_selectable_serial_domain(self):
        """Domain for serials selectable in this wizard.

        - **Normal MO**: only "new" serials (on hand) with a warehouse/location set
        - **Rework MO**: only "warehouse" serials (finished goods) with a warehouse/location set
        """
        self.ensure_one()
        if not self.category_id:
            return [('id', '=', 0)]

        target_state = 'warehouse' if self.is_rework else 'new'
        return [
            ('setsco_category_id', '=', self.category_id.id),
            '|',
            ('product_id', '=', self.product_id.id),
            ('product_id', '=', False),
            ('state', '=', target_state),
        ]

    @api.onchange('use_range_selection')
    def _onchange_use_range_selection(self):
        """Clear range fields when switching modes"""
        if not self.use_range_selection:
            self.start_serial_id = False
            self.end_serial_id = False
        else:
            # Clear individual assignments when switching to range mode
            self.assignment_line_ids = [(5, 0, 0)]

    @api.onchange('start_serial_id', 'end_serial_id')
    def _onchange_range_serials(self):
        """Update assignment lines when range changes"""
        if self.use_range_selection and self.start_serial_id and self.end_serial_id:
            # Validate that end serial comes after start serial
            if self._validate_serial_range():
                self._populate_lines_from_range()
            else:
                self.assignment_line_ids = [(5, 0, 0)]

    @api.onchange('start_serial_scan')
    def _onchange_start_serial_scan(self):
        if self.start_serial_scan and self.category_id:
            serial = self.env['setsco.serial.number'].search(
                [('name', '=', self.start_serial_scan)] + self._get_selectable_serial_domain(),
                limit=1,
            )
            if serial:
                self.start_serial_id = serial
            else:
                self.start_serial_id = False

    @api.onchange('end_serial_scan')
    def _onchange_end_serial_scan(self):
        if self.end_serial_scan and self.category_id:
            serial = self.env['setsco.serial.number'].search(
                [('name', '=', self.end_serial_scan)] + self._get_selectable_serial_domain(),
                limit=1,
            )
            if serial:
                self.end_serial_id = serial
            else:
                self.end_serial_id = False

    @api.onchange('start_serial_scan_input')
    def _onchange_start_serial_scan_input(self):
        """Handle start serial input from scanning or manual entry"""
        if self.start_serial_scan_input and self.category_id:
            # Find the serial by name
            serial = self.env['setsco.serial.number'].search(
                [('name', '=', self.start_serial_scan_input)] + self._get_selectable_serial_domain(),
                limit=1,
            )
            if serial:
                self.start_serial_id = serial
                self.start_serial_scan = self.start_serial_scan_input  # Also update the old field for compatibility
            else:
                self.start_serial_id = False
                # Show warning that serial not found
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for category %s.') % (self.start_serial_scan_input, self.category_id.name)
                    }
                }

    @api.onchange('end_serial_scan_input')
    def _onchange_end_serial_scan_input(self):
        """Handle end serial input from scanning or manual entry"""
        if self.end_serial_scan_input and self.category_id:
            # Find the serial by name
            serial = self.env['setsco.serial.number'].search(
                [('name', '=', self.end_serial_scan_input)] + self._get_selectable_serial_domain(),
                limit=1,
            )
            if serial:
                self.end_serial_id = serial
                self.end_serial_scan = self.end_serial_scan_input  # Also update the old field for compatibility
            else:
                self.end_serial_id = False
                # Show warning that serial not found
                return {
                    'warning': {
                        'title': _('Serial Not Found'),
                        'message': _('Serial number "%s" not found or not available for category %s.') % (self.end_serial_scan_input, self.category_id.name)
                    }
                }

    def _validate_serial_range(self):
        """Validate that the serial range is valid"""
        if not self.start_serial_id or not self.end_serial_id:
            return False
            
        try:
            import re
            start_name = self.start_serial_id.name
            end_name = self.end_serial_id.name
            
            start_match = re.match(r'(.+?)(\d+)$', start_name)
            end_match = re.match(r'(.+?)(\d+)$', end_name)
            
            if not start_match or not end_match:
                return False
            
            start_prefix, start_num_str = start_match.groups()
            end_prefix, end_num_str = end_match.groups()
            
            if start_prefix != end_prefix:
                return False
            
            start_num = int(start_num_str)
            end_num = int(end_num_str)
            
            return start_num <= end_num
        except:
            return False

    @api.depends('start_serial_id', 'end_serial_id', 'quantity', 'use_range_selection')
    def _compute_range_warning(self):
        for wizard in self:
            warning = ""
            if wizard.use_range_selection and wizard.start_serial_id and wizard.end_serial_id and wizard.quantity:
                try:
                    import re
                    start_name = wizard.start_serial_id.name
                    end_name = wizard.end_serial_id.name
                    
                    start_match = re.match(r'(.+?)(\d+)$', start_name)
                    end_match = re.match(r'(.+?)(\d+)$', end_name)
                    
                    if start_match and end_match:
                        start_num = int(start_match.groups()[1])
                        end_num = int(end_match.groups()[1])
                        range_size = end_num - start_num + 1
                        max_quantity = int(wizard.quantity)
                        
                        if range_size > max_quantity:
                            warning = _("Range contains %d serial numbers but only %d are needed. Only the first %d will be used: %s to %s%d.") % (
                                range_size, max_quantity, max_quantity, 
                                start_name, start_match.groups()[0], start_num + max_quantity - 1
                            )
                except:
                    pass
            self._onchange_range_serials()
            wizard.range_warning = warning

    @api.onchange('production_id', 'product_id', 'quantity')
    def _onchange_production_details(self):
        if not self.use_range_selection and self.production_id and self.product_id and self.quantity:
            self._populate_lines_individual()

    def _populate_lines_individual(self):
        """Populate lines with individual serial selection"""
        # Clear existing lines
        self.assignment_line_ids = [(5, 0, 0)]
        
        # Calculate remaining quantity needed
        current_serial_count = len(self.production_id.setsco_serial_ids) if self.production_id else 0
        remaining_needed = self.quantity - current_serial_count
        
        if remaining_needed <= 0:
            return  # No more serials needed
        
        # Get available setsco serial numbers for this category
        domain = self._get_selectable_serial_domain()
        available_serials = self.env['setsco.serial.number'].search(domain, order='name ASC')
        
        # Create lines for the remaining quantity needed
        lines = []
        for i in range(int(remaining_needed)):
            line_vals = {
                'sequence': i + 1,
                'setsco_serial_id': available_serials[i].id if i < len(available_serials) else False,
            }
            lines.append((0, 0, line_vals))
        
        self.assignment_line_ids = lines

    def _populate_lines_from_range(self):
        """Populate lines from range selection"""
        if not self.start_serial_id or not self.end_serial_id:
            return
            
        try:
            import re
            start_name = self.start_serial_id.name
            end_name = self.end_serial_id.name
            
            start_match = re.match(r'(.+?)(\d+)$', start_name)
            end_match = re.match(r'(.+?)(\d+)$', end_name)
            
            if not start_match or not end_match:
                return
            
            start_prefix, start_num_str = start_match.groups()
            end_prefix, end_num_str = end_match.groups()
            
            if start_prefix != end_prefix:
                return
            
            start_num = int(start_num_str)
            end_num = int(end_num_str)
            num_length = len(start_num_str)
            
            if start_num > end_num:
                return
            
            # Clear existing lines
            self.assignment_line_ids = [(5, 0, 0)]
            
            # Calculate remaining quantity needed
            current_serial_count = len(self.production_id.setsco_serial_ids) if self.production_id else 0
            remaining_needed = int(self.quantity) - current_serial_count if self.quantity else 0
            
            # Limit range to remaining quantity needed
            range_size = end_num - start_num + 1
            actual_range = min(range_size, remaining_needed)
            
            if actual_range <= 0:
                return
            
            # Generate serial names and find existing setsco serials in range
            lines = []
            _logger.warning("serial_name")
            for i, num in enumerate(range(start_num, start_num + actual_range)):
                serial_name = f"{start_prefix}{num:0{num_length}d}"
                _logger.warning(serial_name)
                # Find existing setsco serial with this name in the same category
                existing_serial = self.env['setsco.serial.number'].search(
                    [('name', '=', serial_name)] + self._get_selectable_serial_domain(),
                    limit=1,
                )
                _logger.warning(existing_serial)
                line_vals = {
                    'sequence': i + 1,
                    'setsco_serial_id': existing_serial.id if existing_serial else False,
                    'serial_name_input': serial_name,
                }
                lines.append((0, 0, line_vals))
            
            self.assignment_line_ids = lines
        except:
            pass

    def action_assign_serials(self):
        """Assign the selected setsco serial numbers to the manufacturing order"""
        self.ensure_one()
        
        if not self.assignment_line_ids:
            raise ValidationError(_('Please add serial number assignments'))
        
        # Check if we're trying to assign more serials than needed
        current_serial_count = len(self.production_id.setsco_serial_ids)
        remaining_needed = self.production_id.product_qty - current_serial_count
        lines_with_serials = len([line for line in self.assignment_line_ids if line.setsco_serial_id or line.serial_name_input])
        
        if lines_with_serials > remaining_needed:
            raise ValidationError(
                _('Cannot assign %d serial numbers. Only %d more serials are needed for production order %s. '
                  'Current: %d, Required: %d, Remaining needed: %d') % 
                (lines_with_serials, remaining_needed, self.production_id.name, 
                 current_serial_count, self.production_id.product_qty, remaining_needed)
            )
        
        serials_to_assign = []
        
        # Process each line
        for line in self.assignment_line_ids:
            if line.setsco_serial_id:
                # Direct assignment
                serials_to_assign.append(line.setsco_serial_id)
            elif line.serial_name_input and self.use_range_selection:
                # Range selection - find the serial by name (with or without product)
                existing_serial = self.env['setsco.serial.number'].search(
                    [('name', '=', line.serial_name_input)] + self._get_selectable_serial_domain(),
                    limit=1,
                )
                
                if existing_serial:
                    serials_to_assign.append(existing_serial)
                else:
                    raise ValidationError(_('Serial number %s not found or not available') % line.serial_name_input)
            else:
                continue

        if not serials_to_assign:
            raise ValidationError(_('No valid serial numbers to assign'))

        # Enforce "warehouse already set" and correct starting state
        expected_state = 'warehouse' if self.is_rework else 'new'
        invalid_state = [s for s in serials_to_assign if s.state != expected_state]

        if invalid_state:
            raise ValidationError(_(
                "Some serial numbers are not in the expected state '%s': %s"
            ) % (expected_state, ', '.join(s.name for s in invalid_state)))
        
        # Update setsco serial numbers
        for serial in serials_to_assign:
            vals = {
                'production_id': self.production_id.id,
                'state': 'manufacturing',
                'manufacturing_date': fields.Datetime.now(),
            }
            # Automatically assign product if not already assigned
            if not serial.product_id:
                vals['product_id'] = self.product_id.id
            serial.write(vals)
            
            # Update location to production source location when assigned to manufacturing
            if self.production_id.location_src_id:
                old_location = serial.location_id
                serial.write({'location_id': self.production_id.location_src_id.id})
                
                # Log the location change for traceability
                if old_location:
                    serial.message_post(
                        body=_('Location moved to production location %s when assigned to manufacturing order %s') % 
                        (self.production_id.location_src_id.name, self.production_id.name)
                    )
                else:
                    serial.message_post(
                        body=_('Location set to production location %s when assigned to manufacturing order %s') % 
                        (self.production_id.location_src_id.name, self.production_id.name)
                    )
        
        # Check safety stock levels after assignment and notify users if needed
        safety_stock_warnings = self._check_safety_stock_levels_and_notify()
        
        # No popup notification needed - notifications are sent via category chatter
        return {
            'type': 'ir.actions.act_window_close'
        }

    def _check_safety_stock_levels_and_notify(self):
        """Check safety stock levels after assignment and notify configured users if needed"""
        # Get all setsco categories that have safety stock levels configured
        categories_with_safety_stock = self.env['setsco.category'].search([
            ('safety_stock_level', '>', 0)
        ])
        
        if not categories_with_safety_stock:
            return False
            
        # Get notification users from company settings
        company = self.env.company
        notification_users = company.safety_stock_notification_users
        
        if not notification_users:
            return False
            
        notification_user_ids = notification_users.ids
        
        if not notification_user_ids:
            return False
            
        safety_stock_violations = []
        
        # Check each category for safety stock violations
        for category in categories_with_safety_stock:
            # Count available serials (new state) for this category
            available_serials_count = self.env['setsco.serial.number'].search_count([
                ('setsco_category_id', '=', category.id),
                ('state', '=', 'new')
            ])
            
            # Check if below safety stock level
            if available_serials_count < category.safety_stock_level:
                safety_stock_violations.append(category)
                # Send notification to configured users
                self._send_safety_stock_notification(category, available_serials_count, notification_user_ids)
        
        return len(safety_stock_violations) > 0

    def _send_safety_stock_notification(self, category, current_stock, user_ids):
        """Send safety stock notification by ensuring notification users are category followers and scheduling activities"""
        # Ensure notification users are followers of the category
        notification_users = self.env['res.users'].browse(user_ids)
        
        for user in notification_users:
            if user.exists() and user.active:
                # Check if user is already a follower of the category
                if not category.message_follower_ids.filtered(lambda f: f.partner_id == user.partner_id):
                    # Add user as follower if not already following
                    category.message_subscribe(partner_ids=[user.partner_id.id])
                
                # Check if there are already pending activities for this user on this category
                pending_activities = self.env['mail.activity'].search([
                    ('res_model', '=', 'setsco.category'),
                    ('res_id', '=', category.id),
                    ('user_id', '=', user.id),
                    ('activity_type_id.category', '=', 'default'),
                    ('state', '=', 'planned')
                ])
                
                # Only schedule new activity if there are no pending activities
                if not pending_activities:
                    # Schedule activity for the user on the category
                    category.activity_schedule(
                        'mail_activity_data_todo',
                        user_id=user.id,
                        note=_(
                            '⚠️ SAFETY STOCK ALERT ⚠️\n\n'
                            'Category: %s\n'
                            'Current Stock: %d\n'
                            'Safety Stock Level: %d\n'
                            'Status: BELOW SAFETY STOCK LEVEL\n\n'
                            'This notification was triggered when assigning setsco serial numbers to manufacturing order %s.\n'
                            'Please review inventory levels and take appropriate action.'
                        ) % (category.name, current_stock, category.safety_stock_level, self.production_id.name),
                        summary=_('Safety Stock Alert - %s') % category.name
                    )

        


    def action_scan_start_serial(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'start_serial_scan',
                'wizard_id': self.id,
            }
        }

    def action_scan_end_serial(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_qr_scan',
            'params': {
                'target_field': 'end_serial_scan',
                'wizard_id': self.id,
            }
        }

    def action_update_locations(self):
        """Manually update locations for all setsco serial numbers"""
        self.ensure_one()
        
        # Get all setsco serials for this product/category
        domain = []
        if self.product_id:
            domain.append(('product_id', '=', self.product_id.id))
        if self.category_id:
            domain.append(('category_id', '=', self.category_id.id))
            
        serials = self.env['setsco.serial.number'].search(domain)
        
        if not serials:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No setsco serial numbers found to update.'),
                    'type': 'warning',
                }
            }
        
        # Update locations
        updated_count = serials._batch_update_locations()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Successfully updated locations for %d setsco serial numbers.') % updated_count,
                'type': 'success',
            }
        }

    def update_scan_field(self, field_name, value):
        """Update scan field and trigger onchange logic"""
        # Check if the record still exists
        if not self.exists():
            raise ValidationError(_('The wizard session has expired. Please reopen the wizard and try again.'))
        
        self.ensure_one()
        
        # Update the scan field
        self.write({field_name: value})
        
        # Manually trigger the onchange logic
        if field_name == 'start_serial_scan':
            self._onchange_start_serial_scan()
        elif field_name == 'end_serial_scan':
            self._onchange_end_serial_scan()
        
        return True

    def check_wizard_exists(self, wizard_id):
        """Check if a wizard record exists and return its data"""
        wizard = self.browse(wizard_id)
        if wizard.exists():
            return {
                'exists': True,
                'id': wizard.id,
                'production_id': wizard.production_id.id,
                'product_id': wizard.product_id.id,
            }
        else:
            return {
                'exists': False,
                'message': 'Wizard session has expired. Please reopen the wizard.'
            }

    def _find_serial_by_name(self, serial_name):
        """Find serial by name constrained by product/category and availability"""
        if not serial_name:
            return False
        return self.env['setsco.serial.number'].search(
            [('name', '=', serial_name)] + self._get_selectable_serial_domain(),
            limit=1,
        )

    def _add_assignment_line(self, serial):
        """Append a line to assignment_line_ids if not duplicate"""
        if not serial:
            return False
        existing = self.assignment_line_ids.filtered(lambda l: l.setsco_serial_id == serial)
        if existing:
            return False
        self.assignment_line_ids = [(0, 0, {
            'wizard_id': self.id,
            'setsco_serial_id': serial.id,
            'product_id': self.product_id.id,
        })]
        return True

    def add_individual_serial_from_scan(self, serial_number):
        """Add one serial from scanner into assignment_line_ids"""
        serial_number = (serial_number or '').strip()
        serial = self._find_serial_by_name(serial_number)
       
        if not serial:
            return False
        added = self._add_assignment_line(serial)

        if not added:
            return False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Serial %s added to list') % serial_number,
                'type': 'success',
            }
        }

    def set_range_start_serial_from_scan(self, serial_number):
        serial_number = (serial_number or '').strip()
        serial = self._find_serial_by_name(serial_number)
        if not serial:
            return False
        self.start_serial_id = serial.id
        self.start_serial_scan_input = serial.name
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Range start set to %s') % serial_number,
                'type': 'success',
            }
        }

    def set_range_end_serial_from_scan(self, serial_number):
        serial_number = (serial_number or '').strip()
        serial = self._find_serial_by_name(serial_number)
        if not serial:
            return False
        self.end_serial_id = serial.id
        self.end_serial_scan_input = serial.name
        # reuse existing onchange preview logic
        self._onchange_range_serials()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Range end set to %s') % serial_number,
                'type': 'success',
            }
        }

    def action_add_range_to_list(self):
        """Add current preview/range into assignment_line_ids"""
        if not self.start_serial_id or not self.end_serial_id:
            return False
        # Build list between start and end by name
        start = self.start_serial_id.name
        end = self.end_serial_id.name
        import re
        m1 = re.match(r'([A-Za-z]+)(\d+)', start or '')
        m2 = re.match(r'([A-Za-z]+)(\d+)', end or '')
        if not m1 or not m2 or m1.group(1) != m2.group(1):
            return False
        prefix = m1.group(1)
        n1 = int(m1.group(2))
        n2 = int(m2.group(2))
        if n1 > n2:
            n1, n2 = n2, n1
        names = [f"{prefix}{i:05d}" for i in range(n1, n2 + 1)]
        serials = self.env['setsco.serial.number'].search(
            [('name', 'in', names)] + self._get_selectable_serial_domain()
        )
        for s in serials:
            self._add_assignment_line(s)
        # reset range state
        self.start_serial_id = False
        self.end_serial_id = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Range added (%s - %s)') % (start, end),
                'type': 'success',
            }
        }


class SetscoSerialAssignmentWizardLine(models.TransientModel):
    _name = 'setsco.serial.assignment.wizard.line'
    _description = 'Setsco Serial Assignment Wizard Line'

    wizard_id = fields.Many2one('setsco.serial.assignment.wizard', string='Wizard', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', required=True, default=1)
    setsco_serial_id = fields.Many2one('setsco.serial.number', string='Setsco Serial Number')
    product_id = fields.Many2one('product.product', string='Product', related='wizard_id.product_id')
    category_id = fields.Many2one('setsco.category', string='Category', related='wizard_id.category_id')
    
    # For range selection mode
    serial_name_input = fields.Char(string='Expected Serial Name')
    is_available = fields.Boolean(string='Available', compute='_compute_is_available')
    
    serial_name = fields.Char(string='Serial Name', related='setsco_serial_id.name', readonly=True)
    serial_state = fields.Selection(string='Serial State', related='setsco_serial_id.state', readonly=True)

    @api.depends('setsco_serial_id', 'serial_name_input', 'product_id', 'wizard_id.is_rework')
    def _compute_is_available(self):
        for line in self:
            if line.serial_name_input and line.product_id:
                # Check if the expected serial exists and is available (with or without product)
                target_state = 'warehouse' if line.wizard_id.is_rework else 'new'
                existing = self.env['setsco.serial.number'].search([
                    ('name', '=', line.serial_name_input),
                    ('setsco_category_id', '=', line.category_id.id),
                    '|', ('product_id', '=', line.product_id.id), ('product_id', '=', False),
                    ('state', '=', target_state),
                ], limit=1)
                line.is_available = bool(existing)
            else:
                line.is_available = bool(line.setsco_serial_id)