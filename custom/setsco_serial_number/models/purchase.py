from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # setsco Serial Number fields
    is_setsco_serial_purchase = fields.Boolean(string='Purchase Setsco Serial Numbers',
                                               help='Check this to purchase setsco serial numbers for this product')
    setsco_serial_ids = fields.One2many('setsco.serial.number', 'purchase_order_line_id',
                                        string='Setsco Serial Numbers')
    setsco_serial_count = fields.Integer(string='setsco Serial Count',
                                         compute='_compute_setsco_serial_count')
    expected_setsco_serials = fields.Text(string='Expected Serial Numbers',
                                          help='List expected serial numbers to be received (one per line)')

    @api.depends('setsco_serial_ids')
    def _compute_setsco_serial_count(self):
        for line in self:
            line.setsco_serial_count = len(line.setsco_serial_ids)

    @api.onchange('is_setsco_serial_purchase', 'product_qty')
    def _onchange_setsco_serial_purchase(self):
        if self.is_setsco_serial_purchase and self.product_qty:
            # Suggest creating placeholders for expected serial numbers
            if not self.expected_setsco_serials:
                serials = []
                for i in range(int(self.product_qty)):
                    serials.append(f"SERIAL_{i+1:03d}")
                self.expected_setsco_serials = '\n'.join(serials)

    def action_create_setsco_serials(self):
        """Create setsco serial numbers from expected serials"""
        self.ensure_one()
        if not self.is_setsco_serial_purchase:
            raise ValidationError(_('This line is not marked for setsco serial purchase'))
        
        if not self.expected_setsco_serials:
            raise ValidationError(_('Please specify expected serial numbers'))
        
        serial_lines = self.expected_setsco_serials.strip().split('\n')
        serial_lines = [line.strip() for line in serial_lines if line.strip()]
        
        if len(serial_lines) != int(self.product_qty):
            raise ValidationError(_('Number of serial numbers (%d) must match quantity (%d)') % 
                                (len(serial_lines), int(self.product_qty)))
        
        created_serials = []
        for serial_name in serial_lines:
            # Check if serial already exists for this product
            existing = self.env['setsco.serial.number'].search([
                ('name', '=', serial_name),
                ('product_id', '=', self.product_id.id)
            ])
            if existing:
                raise ValidationError(_('Serial number %s already exists for product %s') % 
                                    (serial_name, self.product_id.name))
            
            serial = self.env['setsco.serial.number'].create({
                'name': serial_name,
                'product_id': self.product_id.id,
                'purchase_order_line_id': self.id,
                'state': 'purchased',
            })
            created_serials.append(serial)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Setsco Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [s.id for s in created_serials])],
            'context': {'create': False}
        }

    def action_view_setsco_serials(self):
        """View setsco serial numbers for this purchase line"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Setsco Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('purchase_order_line_id', '=', self.id)],
            'context': {
                'default_purchase_order_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_state': 'purchased'
            }
        }


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    has_setsco_serials = fields.Boolean(string='Has Setsco Serial Numbers',
                                        compute='_compute_has_setsco_serials', store=True)
    setsco_serial_count = fields.Integer(string='Total Setsco Serials',
                                         compute='_compute_setsco_serial_count')

    @api.depends('order_line.product_id')
    def _compute_has_setsco_serials(self):
        for order in self:
            order.has_setsco_serials = any(line.product_id.is_setsco_label for line in order.order_line)

    @api.depends('order_line.setsco_serial_ids')
    def _compute_setsco_serial_count(self):
        for order in self:
            order.setsco_serial_count = sum(len(line.setsco_serial_ids) for line in order.order_line)

    def action_view_all_setsco_serials(self):
        """View all setsco serial numbers for this purchase order"""
        self.ensure_one()
        serial_ids = []
        for line in self.order_line:
            serial_ids.extend(line.setsco_serial_ids.ids)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order Setsco Serial Numbers'),
            'res_model': 'setsco.serial.number',
            'view_mode': 'list,form',
            'domain': [('id', 'in', serial_ids)],
            'context': {'create': False}
        } 