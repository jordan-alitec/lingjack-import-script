# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    work_order_ids = fields.One2many(
        'sale.work.order',
        'sale_order_id',
        string='Work Orders',
        readonly=True,
        help='Manufacturing work orders created from this sale order'
    )
    
    work_order_count = fields.Integer(
        string='Work Order Count',
        compute='_compute_work_order_count'
    )
    
    @api.depends('work_order_ids')
    def _compute_work_order_count(self):
        for record in self:
            record.work_order_count = len(record.work_order_ids)

    def action_confirm_no_workorder(self):
        """Confirm sale order without creating work orders
        This method is to be used in data migration script only - to be removed later"""
        return super().action_confirm()

    def action_confirm(self):
        """Override to create work orders for manufacturing products"""
        result = super().action_confirm()
        self._create_work_orders()
        return result
    
    def _create_work_orders(self):
        """Create work orders for order lines with manufacturing products"""
        manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)

        if not manufacture_route:
            return

        # Group order lines by customer requirements (e.g., delivery date, priority)
        grouped_lines = {}
        for line in self.order_line:

            if (line.product_id.type == 'consu' and line.product_id.route != 'buy'):
                
                key = (line.commitment_date if line.commitment_date else fields.Datetime.now())
                if key not in grouped_lines:
                    grouped_lines[key] = []
                grouped_lines[key].append(line)
        # Create work orders for each group
        for (request_date), lines in grouped_lines.items():
            work_order_vals = {
                'sale_order_id': self.id,
                'request_date': request_date ,
                'state': 'draft',
                'company_id': self.company_id.id,
                'line_ids': [(0, 0, {
                    'sale_line_id': line.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom_id': line.product_uom.id,
                    'state': 'draft'
                }) for line in lines]
            }
            
            work_order = self.env['sale.work.order'].create(work_order_vals)
    
    def action_view_work_orders(self):
        """View related work orders"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("lingjack_sale_workorder.action_sale_work_order")

        if len(self.work_order_ids) > 1:
            action['domain'] = [('id', 'in', self.work_order_ids.ids)]
        elif len(self.work_order_ids) == 1:
            action['views'] = [(self.env.ref('lingjack_sale_workorder.view_sale_work_order_form').id, 'form')]
            action['res_id'] = self.work_order_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        
        return action

    def action_open_time_tracking_gantt(self):
        """ Method to open the Gantt view of productivity records (time tracking) related to this sale order """
        self.ensure_one()
        
        # Get all productivity records from all work orders of all MRP productions related to this sale order
        productivity_ids = [0]
        
        # Get all MRP productions related to this sale order through work orders
        mrp_productions = self.work_order_ids.mapped('production_ids')
        
        # Get all work orders from these productions
        workorders = mrp_productions.mapped('workorder_ids')
        
        # Get all productivity records from these work orders
        if workorders:
            productivity_ids = workorders.mapped('time_ids').ids
        action = {
            'name': f'Time Tracking - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'gantt,list,form',
            'view_id': self.env.ref('lingjack_shop_floor.view_mrp_workcenter_productivity_gantt_time_tracking').id,
            'search_view_id': self.env.ref('lingjack_shop_floor.view_mrp_workcenter_productivity_search_time_tracking').id,
            'domain': [('id', 'in', productivity_ids)] if productivity_ids else [('id', '=', 0)],
            # 'context': {
            #     'default_workorder_id': workorders[0].id if workorders else False,
            #     'group_by': 'production_id,workorder_id',
            #     'search_default_group_by_production': 1,
            #     'search_default_group_by_workorder': 1,
            #     'search_default_include_workorders_without_tracking': 1,
            #     'search_default_sale_work_order_filter': 1,
            # },
            'target': 'current',
            'help': _("""
                <p class="o_view_nocontent_smiling_face">
                    No time tracking records found
                </p>
                <p>
                    This view shows time tracking sessions for work orders related to this sale order.
                    Work orders without time tracking are also displayed in blue.
                </p>
            """),
        }
        # return action
        return action



class SaleWorkOrderLine(models.Model):
    _name = 'sale.work.order.line'
    _description = 'Sale Work Order Line'
    _order = 'sequence, id'
    
    sequence = fields.Integer(string='Sequence', default=10)
    display_name = fields.Char(compute='_compute_display_name')

    work_order_id = fields.Many2one(
        'sale.work.order',
        string='Work Order',
        required=True,
        ondelete='cascade'
    )
    sale_order_id = fields.Many2one('sale.order', string="Sale Order", related='work_order_id.sale_order_id')

    cs_in_charge_id = fields.Many2one(
        'res.users',
        string='CS In Charge',
        related='sale_order_id.cs_in_charge_id',
        readonly=True,
        store=True,
        help='Customer Service person in charge of this sale order'
    )

    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=False,
        readonly=False,
        ondelete='cascade',
        domain="[('order_id', '=', sale_order_id),('product_id.route', '!=', 'buy')]"
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('route', '!=', 'buy')],
        readonly=False
    )
    
    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        readonly=True
    )
    
    product_qty = fields.Float(
        string='Quantity',
        digits='Product Unit of Measure',
        required=True,
    )
    
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
        readonly=False
    )
    
    production_ids = fields.Many2many(
        'mrp.production',
        'mrp_production_sale_work_order_line_rel',
        'work_order_line_id',
        'production_id',
        string='Manufacturing Orders',
        readonly=True,
        copy=False,
    )

    production_count = fields.Integer(
        string='Production Count',
        compute='_compute_production_count'
    )
    
    qty_produced = fields.Float(
        string='Quantity Produced',
        digits='Product Unit of Measure',
        compute='_compute_qty_produced',
        store=True
    )
    
    qty_remaining = fields.Float(
        string='Quantity Remaining',
        digits='Product Unit of Measure',
        compute='_compute_qty_remaining',
        store=True
    )

    # This field is used to store the quantity produced in IND4
    old_qty_produced = fields.Float('Old Quantity Produced', default=0.0)
    
    qty_in_stock = fields.Float(
        string='Stored In Qty',
        digits='Product Unit of Measure',
        default=0.0,
        help='Quantity that has been stored in the destination location'
    )
    
    qty_remaining_to_create_swo = fields.Float(
        string='Qty Remaining to Create SWO',
        digits='Product Unit of Measure',
        compute='_compute_qty_remaining_to_create_swo',
        store=True,
        help='Quantity remaining from sale order line that can be used to create new SWOs'
    )
    
    bom_id = fields.Many2one(
        'mrp.bom',
        string='Bill of Materials',
        compute='_compute_bom_id',
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_production', 'In Production'),
        ('produced', 'Produced'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    remarks = fields.Text(
        string='Remarks',
        tracking=True,
        help='Additional notes or special instructions for this product'
    )
    
    quantity_on_hand = fields.Float(
        string='Quantity On Hand',
        compute='_compute_quantities',
        digits='Product Unit of Measure',
        help='Current quantity of products in stock'
    )

    forecast_quantity = fields.Float(
        string='Forecast Quantity',
        compute='_compute_quantities',
        digits='Product Unit of Measure',
        help='Forecasted quantity including incoming and outgoing moves'
    )

    # SFP Distribution fields
    destination_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        domain="[('usage', '=', 'internal')]",
        help='Location where finished products should be stored after manufacturing'
    )

    destination_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Destination Warehouse',
        check_company=True,
        help='Location where finished products should be stored after manufacturing'
    )

    has_custom_destination = fields.Boolean(
        string='Has Custom Destination',
        compute='_compute_has_custom_destination',
        store=True
    )

    @api.depends('work_order_id')
    def _compute_display_name(self):
        _logger.warning(f"compute display name")
        for record in self:
            record.display_name = f"{record.work_order_id.name}"

    @api.depends('production_ids')
    def _compute_production_count(self):
        for record in self:
            record.production_count = len(record.production_ids)
    
    @api.depends('production_ids.qty_produced')
    def _compute_qty_produced(self):
        for record in self:
            record.qty_produced = sum(record.production_ids.mapped('qty_produced')) + record.old_qty_produced
    
    @api.depends('product_qty', 'qty_produced', 'qty_in_stock')
    def _compute_qty_remaining(self):
        for record in self:
            record.qty_remaining = record.product_qty - record.qty_produced
    
    @api.depends('sale_line_id', 'sale_line_id.product_uom_qty', 'work_order_id.sale_order_id.work_order_ids.line_ids.product_qty')
    def _compute_qty_remaining_to_create_swo(self):
        """Compute quantity remaining from sale order line that can be used to create new SWOs"""
        for record in self:
            if not record.sale_line_id:
                record.qty_remaining_to_create_swo = 0.0
                continue
            
            # Get the total quantity from the sale order line
            sale_line_qty = record.sale_line_id.product_uom_qty
            
            # Get all SWO lines linked to this sale order line
            swo_lines = self.env['sale.work.order.line'].search([
                ('sale_line_id', '=', record.sale_line_id.id),
                ('state', '!=', 'cancelled')
            ])
            
            # Calculate total quantity already allocated to SWOs
            total_allocated_qty = sum(swo_lines.mapped('product_qty'))
            
            # Calculate remaining quantity
            record.qty_remaining_to_create_swo = sale_line_qty - total_allocated_qty
    
    @api.depends('product_id')
    def _compute_bom_id(self):
        for record in self:
            if record.product_id:
                try:
                    bom_by_product = self.env['mrp.bom']._bom_find(
                        products=record.product_id,
                        company_id=record.work_order_id.company_id.id
                    )
                    bom = bom_by_product[record.product_id] if record.product_id in bom_by_product else self.env['mrp.bom']
                    record.bom_id = bom.id if bom else False
                except Exception:
                    # Fallback: search for BOM manually
                    bom = self.env['mrp.bom'].search([
                        ('product_tmpl_id', '=', record.product_id.product_tmpl_id.id),
                        ('product_id', '=', record.product_id.id),
                        ('type', '=', 'normal'),
                        ('active', '=', True),
                        ('company_id', '=', record.work_order_id.company_id.id)
                    ], limit=1)
                    record.bom_id = bom.id if bom else False
            else:
                record.bom_id = False
    def compute_state(self):
        '''
        This function is to manually click compute from form view 
        '''
        for rec in self:
            rec._compute_state()

    @api.constrains('production_ids', 'qty_in_stock', 'qty_produced')
    def _compute_state(self):
        for record in self:
            state = 'draft'

            if record.production_ids:
                if all(mo.state == 'cancel' for mo in record.production_ids):
                    state = 'confirmed'

                elif all(mo.state == 'done' for mo in record.production_ids):
                    if record.qty_in_stock >= record.product_qty:
                        state = 'delivered'
                    elif record.qty_produced >= record.product_qty:
                        state = 'produced'
                    else:
                        state = 'in_production'
                else:
                    state = 'in_production'
            else:
                if record.qty_in_stock >= record.product_qty:
                    state = 'delivered'
                elif record.qty_produced >= record.product_qty:
                    state = 'produced'
                
            record.state = state

            if record.work_order_id:
                record.work_order_id._compute_state()


    @api.constrains('product_id', 'product_qty')
    def _check_modification_allowed(self):
        """Prevent modifications once MOs are created"""
        for record in self:
            if record.production_ids and record.state != 'draft':
                raise ValidationError(_('Cannot modify line once manufacturing orders have been created.'))
    
    @api.constrains('product_qty', 'sale_line_id')
    def _check_qty_not_exceed_sale_line(self):
        """Ensure product_qty does not exceed remaining quantity from sale order line"""
        for record in self:
            if record.sale_line_id and record.state in ['draft', 'confirmed']:
                # Calculate remaining quantity excluding current record
                sale_line_qty = record.sale_line_id.product_uom_qty
                other_swo_lines = self.env['sale.work.order.line'].search([
                    ('sale_line_id', '=', record.sale_line_id.id),
                    ('id', '!=', record.id),
                    ('state', '!=', 'cancelled')
                ])
                total_other_qty = sum(other_swo_lines.mapped('product_qty'))
                max_allowed_qty = sale_line_qty - total_other_qty
                
                if record.product_qty > max_allowed_qty:
                    raise ValidationError(
                        _('Product quantity (%s) cannot exceed remaining quantity from sale order line (%s). '
                          'Remaining quantity: %s') % (
                            record.product_qty, 
                            record.sale_line_id.name,
                            max_allowed_qty
                        )
                    )
    
    @api.onchange('sale_line_id')
    def _onchange_sale_line_id(self):
        """Auto-populate product_id and product_qty when sale_line_id is selected"""
        if self.sale_line_id:
            self.product_id = self.sale_line_id.product_id
            self.product_uom_id = self.sale_line_id.product_uom.id
            # Set quantity to remaining quantity from sale order line
            self.product_qty = self.qty_remaining_to_create_swo

    def write(self, vals):
        """Override write to prevent modifications in certain states"""
        for record in self:
            if record.state in ['in_production', 'produced', 'delivered'] and \
               any(field in vals for field in ['product_id', 'product_qty']):
                raise ValidationError(_('Cannot modify product details once manufacturing has started.'))
        return super().write(vals)

    def action_create_production(self):
        """Create manufacturing order from this work order line"""
        self.ensure_one()
        
        if self.qty_remaining <= 0:
            raise UserError(_('No remaining quantity to produce.'))
        
        # Get the sale order and its procurement group
        sale_order = self.work_order_id.sale_order_id
        # if not sale_order.procurement_group_id:
        #     group = self.env['procurement.group'].create({
        #         'name': sale_order.name,
        #         'move_type': sale_order.picking_policy,
        #         'sale_id': sale_order.id,
        #         'partner_id': sale_order.partner_shipping_id.id,
        #     })
        #     sale_order.procurement_group_id = group.id
        #
        production_vals = {
            'product_id': self.product_id.id,
            'product_qty': self.qty_remaining,
            'product_uom_id': self.product_uom_id.id,
            'origin': f"{sale_order.name} - {self.work_order_id.name}",
            'company_id': self.work_order_id.company_id.id,
            'sale_work_order_ids': [(4, self.work_order_id.id)],
            'sale_work_order_line_ids': [(4, self.id)],
            'sale_order_ids': [(4, sale_order.id)],
            # 'procurement_group_id': sale_order.procurement_group_id.id,
            # 'user_id': sale_order.user_id.id,
            'date_start': self.work_order_id.request_date,
        }
        
        production = self.env['mrp.production'].create(production_vals)
        self.write({
            'state': 'in_production',
            'production_ids': [(4, production.id)]
        })

        production._compute_bom_id()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Manufacturing Order'),
            'res_model': 'mrp.production',
            'res_id': production.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_time_tracking_gantt(self):
        """ Method to open the Gantt view of productivity records (time tracking) related to this work order line """
        self.ensure_one()
        
        # Get all productivity records from all work orders of all MRP productions related to this work order line
        productivity_ids = [0]
        
        # Get all MRP productions related to this work order line
        mrp_productions = self.production_ids
        
        # Get all work orders from these productions
        workorders = mrp_productions.mapped('workorder_ids')
        
        # Get all productivity records from these work orders
        if workorders:
            productivity_ids = workorders.mapped('time_ids').ids

        action = {
            'name': f'Time Tracking - {self.work_order_id.name} - {self.product_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'gantt,list,form',
            'views': [
                (self.env.ref('lingjack_shop_floor.view_mrp_workcenter_productivity_gantt_time_tracking').id, 'gantt'),
                (False, 'list'),
                (False, 'form')
            ],
            'domain': [('id', 'in', productivity_ids)] if productivity_ids else [('id','=',0)],
            'context': {
                'default_workorder_id': workorders[0].id if workorders else False,
                'group_by': 'production_id,workorder_id',
                'search_default_group_by_production': 1,
                'search_default_group_by_workorder': 1,
                'search_default_include_workorders_without_tracking': 1,
                'search_default_sale_work_order_filter': 1,
            },
            'target': 'current',
            'help': _("""
                <p class="o_view_nocontent_smiling_face">
                    No time tracking records found
                </p>
                <p>
                    This view shows time tracking sessions for work orders related to this work order line.
                    Work orders without time tracking are also displayed in blue.
                </p>
            """),
        }
        return action

    @api.depends('product_id')
    def _compute_quantities(self):
        for record in self:
            if not record.product_id:
                record.quantity_on_hand = 0.0
                record.forecast_quantity = 0.0
                continue

            # Get quantities from stock quants
            quants = self.env['stock.quant'].search([
                ('product_id', '=', record.product_id.id),
                ('location_id.usage', '=', 'internal')
            ])
            record.quantity_on_hand = sum(quants.mapped('quantity'))

            # Get forecast quantity
            stock_moves = self.env['stock.move'].search([
                ('product_id', '=', record.product_id.id),
                ('state', 'not in', ['done', 'cancel']),
                ('location_dest_id.usage', '=', 'internal')
            ])
            incoming = sum(stock_moves.mapped('product_qty'))

            stock_moves = self.env['stock.move'].search([
                ('product_id', '=', record.product_id.id),
                ('state', 'not in', ['done', 'cancel']),
                ('location_id.usage', '=', 'internal')
            ])
            outgoing = sum(stock_moves.mapped('product_qty'))

            record.forecast_quantity = record.quantity_on_hand + incoming - outgoing

            record.product_uom_id = record.product_id.uom_id.id

    @api.depends('destination_location_id')
    def _compute_has_custom_destination(self):
        for record in self:
            record.has_custom_destination = bool(record.destination_location_id)

    @api.constrains('destination_warehouse_id')
    def update_warehouse_store_location(self):
        '''
        Update the destination store location based on the destination warehouse
        '''
        for record in self:
            if record.destination_warehouse_id:
                record.destination_location_id = record.destination_warehouse_id.lot_stock_id.id



class SaleWorkOrder(models.Model):
    _name = 'sale.work.order'
    _description = 'Sale Work Order for Manufacturing Planning'
    _order = 'request_date desc, create_date desc'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=False,
        readonly=False,
        ondelete='cascade'
    )
    
    line_ids = fields.One2many(
        'sale.work.order.line',
        'work_order_id',
        string='Work Order Lines'
    )
    
    request_date = fields.Datetime(
        string='Request Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='Date when manufacturing is requested'
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='sale_order_id.partner_id',
        readonly=False,
        store=True
    )
    
    cs_in_charge_id = fields.Many2one(
        'res.users',
        string='CS In Charge',
        related='sale_order_id.cs_in_charge_id',
        readonly=True,
        store=True,
        help='Customer Service person in charge of this sale order'
    )
    
    remarks = fields.Text(
        string='Remarks',
        help='Additional notes or special instructions for production'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_production', 'In Production'),
        ('produced', 'Produced'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    production_ids = fields.Many2many(
        'mrp.production',
        'mrp_production_sale_work_order_rel',
        'work_order_id',
        'production_id',
        string='Manufacturing Orders',
        readonly=True
    )
    
    production_count = fields.Integer(
        string='Production Count',
        compute='_compute_production_count'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    has_pending_mo = fields.Boolean(
        string='Has Lines Without MO',
        compute='_compute_has_pending_mo',
        store=True,
        help='Indicates if there are any lines that have not had manufacturing orders created yet'
    )

    pending_mo_count = fields.Integer(
        string='Lines Without MO',
        compute='_compute_has_pending_mo',
        store=True,
        help='Number of lines that have not had manufacturing orders created'
    )

    completion_date = fields.Datetime(
        string='Completion Date',
        help='Date when the work order is completed'
    )

    @api.depends('name', 'sale_order_id')
    def _compute_display_name(self):
        for record in self:
            if record.name and record.name != _('New'):
                record.display_name = f"{record.name} ({record.sale_order_id.name})"
            else:
                # Show draft indicator when no sequence number is assigned yet
                record.display_name = f"Draft Work Order ({record.sale_order_id.name})"
    
    @api.depends('production_ids')
    def _compute_production_count(self):
        for record in self:
            record.production_count = len(record.production_ids)

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        """Update customer and request date when sale order changes"""
        if self.sale_order_id:
            self.request_date = self.sale_order_id.commitment_date or fields.Datetime.now()
            # Don't overwrite lines if they already exist
            if not self.line_ids and self.state == 'draft':
                lines = []
                for line in self.sale_order_id.order_line.filtered(lambda l: l.product_id.type == 'product'):
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom_id': line.product_uom.id,
                        'sale_line_id': line.id,
                        'state': 'draft'
                    }))
                if lines:
                    self.line_ids = lines

    @api.constrains('line_ids')
    def _check_line_ids(self):
        """Ensure at least one line exists"""
        for record in self:
            if record.state != 'draft' and not record.line_ids:
                raise ValidationError(_('At least one work order line is required.'))

    @api.constrains('sale_order_id')
    def _check_sale_order_id(self):
        """Ensure sale order is in proper state"""
        for record in self:
            if record.sale_order_id.state not in ['sale', 'done']:
                raise ValidationError(_('Sale order must be confirmed before creating a work order.'))

    @api.model_create_multi
    def create(self, vals_list):
        """Create sale work orders without generating sequence number in draft state"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                # Keep as 'New' - sequence will be generated only when confirmed
                vals['name'] = _('New')
        return super().create(vals_list)
    
    def action_confirm(self):
        """Confirm the sale work order and all its lines"""
        self.ensure_one()
        
        # Generate sequence number only when confirming
        if self.name == _('New'):
            self.name = self.env['ir.sequence'].next_by_code('sale.work.order') or _('New')
        
        self.write({'state': 'confirmed'})
        self.line_ids.write({'state': 'confirmed'})

        return True

    def action_reset_draft(self):
        """Reset the sale work order to draft state"""
        self.ensure_one()
        if self.state != 'confirmed':
            raise ValidationError(_(f"Only sale work order in Confirmed state can be reset to draft"))
        
        # Reset sequence number to 'New' when going back to draft
        if self.name != _('New'):
            self.name = _('New')
        
        self.write({'state': 'draft'})
        self.line_ids.write({'state': 'draft'})
        return True

    
    def action_cancel(self):
        """Cancel the sale work order and its lines"""
        self.ensure_one()
        if self.production_ids.filtered(lambda p: p.state not in ('draft', 'cancel')):
            raise UserError(_('Cannot cancel work order with active manufacturing orders.'))
        self.write({'state': 'cancelled'})
        self.line_ids.write({'state': 'cancelled'})
        return True
    
    def action_view_productions(self):
        """View related manufacturing orders"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.mrp_production_action")

        if len(self.production_ids) > 1:
            action['domain'] = [('id', 'in', self.production_ids.ids)]
        elif len(self.production_ids) == 1:
            form_view = [(self.env.ref('mrp.mrp_production_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = self.production_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action

    def action_open_time_tracking_gantt(self):
        """ Method to open the Gantt view of productivity records (time tracking) related to the current sale work order """
        self.ensure_one()
        
        # Get all productivity records from all work orders of all MRP productions related to this sale work order
        productivity_ids = [0]
        
        # Get all MRP productions related to this sale work order
        mrp_productions = self.production_ids
        
        # Get all work orders from these productions
        workorders = mrp_productions.mapped('workorder_ids')
        
        # Get all productivity records from these work orders
        if workorders:
            productivity_ids = workorders.mapped('time_ids').ids

        action = {
            'name': f'Time Tracking - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'gantt,list,form',
            'views': [
                (self.env.ref('lingjack_shop_floor.view_mrp_workcenter_productivity_gantt_time_tracking').id, 'gantt'),
                (False, 'list'),
                (False, 'form')
            ],
            'domain': [('id', 'in', productivity_ids)] if productivity_ids else [('id', '=', 0)],
            # 'context': {
            #     'default_workorder_id': workorders[0].id if workorders else False,
            #     'group_by': 'production_id,workorder_id',
            #     'search_default_group_by_production': 1,
            #     'search_default_group_by_workorder': 1,
            #     'search_default_include_workorders_without_tracking': 1,
            #     'search_default_sale_work_order_filter': 1,
            # },
            'target': 'current',
            'help': _("""
                <p class="o_view_nocontent_smiling_face">
                    No time tracking records found
                </p>
                <p>
                    This view shows time tracking sessions for work orders related to this sale work order.
                    Work orders without time tracking are also displayed in blue.
                </p>
            """),
        }
        return action 



    def _compute_state(self):
        """Compute state based on work order lines"""
        for record in self:
            line_states = record.line_ids.mapped('state')
            if not line_states:
                continue

            if all(state in ['produced', 'delivered'] for state in line_states):
                record.state = 'produced'
            elif any(state == 'in_production' for state in line_states):
                record.state = 'in_production'
            elif any(state == 'confirmed' for state in line_states):
                record.state = 'confirmed'
            elif all(state == 'cancelled' for state in line_states):
                record.state = 'cancelled'

    def write(self, vals):
        """Override write to prevent modifications in certain states"""
        for record in self:
            if record.state in ['in_production', 'produced', 'delivered'] and \
               any(field in vals for field in ['sale_order_id', 'line_ids']):
                raise ValidationError(_('Cannot modify work order details once manufacturing has started.'))
        return super().write(vals)

    @api.depends('line_ids', 'line_ids.production_ids', 'line_ids.state')
    def _compute_has_pending_mo(self):
        for record in self:
            # Find lines that are confirmed but have no MOs created
            pending_lines = record.line_ids.filtered(
                lambda l: l.state == 'confirmed' and not l.production_ids
            )
            record.has_pending_mo = bool(pending_lines)
            record.pending_mo_count = len(pending_lines) 