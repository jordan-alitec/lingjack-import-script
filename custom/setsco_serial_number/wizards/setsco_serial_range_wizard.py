from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SetscoSerialRangeWizard(models.TransientModel):
    _name = 'setsco.serial.range.wizard'
    _description = 'Setsco Serial Range Creation Wizard'

    start_serial = fields.Char(string='Start Serial Number', required=True,
                               help='Starting serial number in format like AS00001')
    end_serial = fields.Char(string='End Serial Number', required=True,
                             help='Ending serial number in format like AS00010')
    serial_type = fields.Selection([
        ('tuv', 'TUV'),
        ('setsco', 'Setsco')
    ], string='Serial Type', required=True, default='setsco',
       help='Type of serial numbers to create')
    category_id = fields.Many2one('product.category', string='Product Category', required=False,
                                  help='Product category for the serial numbers')
    setsco_category_id = fields.Many2one('setsco.category', string='Serial Category', required=True,
                                         help='Serial category to link the serial numbers to')
    product_id = fields.Many2one('product.product', string='Product (Optional)',
                                 domain="[('categ_id', '=', setsco_category_id)]")
    state = fields.Selection([
        ('new', 'New'),
        ('warehouse', 'In Warehouse'),
    ], string='Initial State', default='new', required=True)
    
    # Purchase fields
    purchase_order = fields.Many2one('purchase.order', string='Purchase Order', domain="[('has_setsco_serials', '=', True)]")
    use_range = fields.Boolean(string="Use Range", default=True)
    # Preview fields
    preview_count = fields.Integer(string='Preview Count', compute='_compute_preview_count')
    preview_line_ids = fields.One2many('setsco.serial.range.wizard.line', 'wizard_id', string='Preview Serial Numbers')

    @api.onchange('start_serial', 'end_serial')
    def _onchange_serial_range(self):
        """Update preview when serial range changes"""
        self._compute_preview_count()
        self._update_preview_lines()

    def _compute_preview_count(self):
        """Compute the count of serials to be created"""
        try:
            import re
            if self.start_serial and self.end_serial:
                start_match = re.match(r'(.+?)(\d+)$', self.start_serial)
                end_match = re.match(r'(.+?)(\d+)$', self.end_serial)
                
                if start_match and end_match:
                    start_num = int(start_match.groups()[1])
                    end_num = int(end_match.groups()[1])
                    self.preview_count = max(0, end_num - start_num + 1)
                else:
                    self.preview_count = 0
            else:
                self.preview_count = 0
        except:
            self.preview_count = 0

    def _update_preview_lines(self):
        """Update preview lines based on serial range"""
        # Clear existing lines
        self.preview_line_ids = [(5, 0, 0)]
        
        if not self.start_serial or not self.end_serial or self.preview_count == 0:
            return
        
        # if self.preview_count > 100:
        #     return  # Don't show preview for too many items
        
        try:
            import re
            start_match = re.match(r'(.+?)(\d+)$', self.start_serial)
            if start_match:
                prefix, start_num_str = start_match.groups()
                start_num = int(start_num_str)
                num_length = len(start_num_str)
                
                line_vals = []
                for i in range(self.preview_count):
                    serial_name = f"{prefix}{start_num + i:0{num_length}d}"
                    line_vals.append((0, 0, {
                        'sequence': i + 1,
                        'serial_name': serial_name,
                        'wizard_id': self.id,
                    }))
                
                self.preview_line_ids = line_vals
        except:
            pass

    def action_create_serials(self):
        """Create the range of serial numbers"""
        self.ensure_one()
        
        if not self.preview_line_ids:
            raise ValidationError(_('No serial numbers to create. Please check your input.'))
        

        
        # Create serial numbers from preview lines
        created_serials = []
        for line in self.preview_line_ids:
            # Check if serial already exists in the same category
            existing = self.env['setsco.serial.number'].search([
                ('name', '=', line.serial_name),
                ('category_id', '=', self.category_id.id)
            ])
            if existing:
                continue  # Skip existing serials
            
            vals = {
                'name': line.serial_name,
                'serial_type': self.serial_type,
                'category_id': self.category_id.id,
                'setsco_category_id': self.setsco_category_id.id,
                'product_id': self.product_id.id if self.product_id else None,
                'state': self.state,
            }
            
            if self.purchase_order:
                vals['purchase_order_id'] = self.purchase_order.id
            
            serial = self.env['setsco.serial.number'].create(vals)
            created_serials.append(serial)
        
        if not created_serials:
            raise ValidationError(_('No serial numbers were created. They may already exist.'))
        
        # Return action to view created serials
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [s.id for s in created_serials])],
            'context': {'create': False}
        }


class SetscoSerialProductAssignmentWizard(models.TransientModel):
    _name = 'setsco.serial.product.assignment.wizard'
    _description = 'Setsco Serial Product Assignment Wizard'

    setsco_serial_id = fields.Many2one('setsco.serial.number', string='Serial Number', required=True)
    current_product_id = fields.Many2one('product.product', string='Current Product', 
                                         related='setsco_serial_id.product_id', readonly=True)
    new_product_id = fields.Many2one('product.product', string='New Product', required=True,
                                     domain="[('categ_id', '=', setsco_serial_id.category_id)]")

    def action_assign_product(self):
        """Assign the product to the serial number"""
        self.ensure_one()
        
        # Check if product belongs to the same category as the serial
        if self.new_product_id.categ_id != self.setsco_serial_id.category_id:
            raise ValidationError(_('Product %s does not belong to category %s') % 
                                (self.new_product_id.name, self.setsco_serial_id.category_id.name))
        
        # Check if product is already assigned to another serial with same name in the same category
        existing = self.env['setsco.serial.number'].search([
            ('name', '=', self.setsco_serial_id.name),
            ('category_id', '=', self.setsco_serial_id.category_id.id),
            ('product_id', '=', self.new_product_id.id),
            ('id', '!=', self.setsco_serial_id.id)
        ])
        
        if existing:
            raise ValidationError(_('Serial number %s already exists for product %s in category %s') % 
                                (self.setsco_serial_id.name, self.new_product_id.name, self.setsco_serial_id.category_id.name))
        
        self.setsco_serial_id.product_id = self.new_product_id
        
        return {'type': 'ir.actions.act_window_close'}


class SetscoSerialRangeWizardLine(models.TransientModel):
    _name = 'setsco.serial.range.wizard.line'
    _description = 'Setsco Serial Range Wizard Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('setsco.serial.range.wizard', string='Wizard', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=1)
    serial_name = fields.Char(string='Serial Number', required=True)
    exists = fields.Boolean(string='Already Exists', compute='_compute_exists')

    @api.depends('serial_name', 'wizard_id.category_id')
    def _compute_exists(self):
        for line in self:
            if line.serial_name and line.wizard_id.category_id:
                existing = self.env['setsco.serial.number'].search([
                    ('name', '=', line.serial_name),
                    ('category_id', '=', line.wizard_id.category_id.id)
                ], limit=1)
                line.exists = bool(existing)
            else:
                line.exists = False


class SetscoSerialRangeMigrationWizardLine(models.TransientModel):
    _name = 'setsco.serial.range.migration.wizard.line'
    _description = 'Setsco Serial Range Migration Wizard Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'setsco.serial.range.migration.wizard', string='Wizard', required=True, ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=1)
    serial_name = fields.Char(string='Serial Number', required=True)
    exists = fields.Boolean(string='Already Exists', compute='_compute_exists')

    @api.depends('serial_name', 'wizard_id.setsco_category_id')
    def _compute_exists(self):
        for line in self:
            if line.serial_name and line.wizard_id.setsco_category_id:
                existing = self.env['setsco.serial.number'].search([
                    ('name', '=', line.serial_name),
                    ('setsco_category_id', '=', line.wizard_id.setsco_category_id.id)
                ], limit=1)
                line.exists = bool(existing)
            else:
                line.exists = False


class SetscoSerialRangeMigrationWizard(models.TransientModel):
    _name = 'setsco.serial.range.migration.wizard'
    _description = 'Setsco Serial Range Creation Wizard (Migration)'

    start_serial = fields.Char(
        string='Start Serial Number', required=True,
        help='Starting serial number in format like AS00001'
    )
    end_serial = fields.Char(
        string='End Serial Number', required=True,
        help='Ending serial number in format like AS00010'
    )
    serial_type = fields.Selection([
        ('tuv', 'TUV'),
        ('setsco', 'Setsco')
    ], string='Serial Type', required=True, default='setsco',
       help='Type of serial numbers to create')
    setsco_category_id = fields.Many2one(
        'setsco.category', string='Serial Category', required=True,
        help='Serial category to link the serial numbers to'
    )
    product_id = fields.Many2one(
        'product.product', string='Product (Optional)',
        domain="[('setsco_category_id', '=', setsco_category_id)]",
        help='Attach all created serials to this product'
    )
    location_id = fields.Many2one(
        'stock.location', string='Location (Optional)',
        help='Set this location on all created serials'
    )
    state = fields.Selection([
        ('new', 'New'),
        ('warehouse', 'In Warehouse'),
    ], string='Initial State', default='new', required=True)

    purchase_order = fields.Many2one(
        'purchase.order', string='Purchase Order',
        domain="[('has_setsco_serials', '=', True)]"
    )
    use_range = fields.Boolean(string='Use Range', default=True)
    remarks = fields.Text(string='Remarks', help='Remarks to set on all created serial numbers')

    preview_count = fields.Integer(string='Preview Count', compute='_compute_preview_count')
    preview_line_ids = fields.One2many(
        'setsco.serial.range.migration.wizard.line', 'wizard_id',
        string='Preview Serial Numbers'
    )

    @api.onchange('start_serial', 'end_serial')
    def _onchange_serial_range(self):
        self._compute_preview_count()
        self._update_preview_lines()

    def _compute_preview_count(self):
        try:
            import re
            if self.start_serial and self.end_serial:
                start_match = re.match(r'(.+?)(\d+)$', self.start_serial)
                end_match = re.match(r'(.+?)(\d+)$', self.end_serial)
                if start_match and end_match:
                    start_num = int(start_match.groups()[1])
                    end_num = int(end_match.groups()[1])
                    self.preview_count = max(0, end_num - start_num + 1)
                else:
                    self.preview_count = 0
            else:
                self.preview_count = 0
        except Exception:
            self.preview_count = 0

    def _update_preview_lines(self):
        self.preview_line_ids = [(5, 0, 0)]
        if not self.start_serial or not self.end_serial or self.preview_count == 0:
            return
        try:
            import re
            start_match = re.match(r'(.+?)(\d+)$', self.start_serial)
            if start_match:
                prefix, start_num_str = start_match.groups()
                start_num = int(start_num_str)
                num_length = len(start_num_str)
                line_vals = []
                for i in range(self.preview_count):
                    serial_name = f"{prefix}{start_num + i:0{num_length}d}"
                    line_vals.append((0, 0, {
                        'sequence': i + 1,
                        'serial_name': serial_name,
                        'wizard_id': self.id,
                    }))
                self.preview_line_ids = line_vals
        except Exception:
            pass

    def action_create_serials(self):
        self.ensure_one()
        if not self.preview_line_ids:
            raise ValidationError(_('No serial numbers to create. Please check your input.'))

        created_serials = []
        for line in self.preview_line_ids:
            existing = self.env['setsco.serial.number'].search([
                ('name', '=', line.serial_name),
                ('setsco_category_id', '=', self.setsco_category_id.id)
            ])
            if existing:
                continue

            vals = {
                'name': line.serial_name,
                'serial_type': self.serial_type,
                'setsco_category_id': self.setsco_category_id.id,
                'product_id': self.product_id.id if self.product_id else None,
                'state': self.state,
            }
            if self.product_id:
                vals['category_id'] = self.product_id.categ_id.id
            if self.location_id:
                vals['location_id'] = self.location_id.id
            if self.purchase_order:
                vals['purchase_order_id'] = self.purchase_order.id
            if self.remarks:
                vals['notes'] = self.remarks

            serial = self.env['setsco.serial.number'].create(vals)
            created_serials.append(serial)

        if not created_serials:
            raise ValidationError(_('No serial numbers were created. They may already exist.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [s.id for s in created_serials])],
            'context': {'create': False}
        }