import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)


class ShopFloorProductionComponentPicker(models.TransientModel):
    _name = 'shop.floor.production.component.picker'
    _description = 'Shop Floor Production Component Picker'

    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',
        required=True,
        readonly=True
    )

    planned_production_qty = fields.Float(
        string='Planned Production Quantity',
        digits='Product Unit of Measure',
        default=0.0,
        help='Quantity planned to produce - will auto-calculate component requirements'
    )

    max_possible_qty = fields.Float(
        string='Maximum Possible Quantity',
        digits='Product Unit of Measure',
        compute='_compute_max_possible_qty',
        help='Maximum quantity that can be produced with available components'
    )

    max_remaining_qty = fields.Float(
        string='Maximum Remaining Quantity',
        digits='Product Unit of Measure',
        compute='_compute_max_remaining_qty',
        help='Maximum quantity that can be produced considering remaining production needs (product_uom_qty - qty_producing)'
    )

    production_remaining_qty = fields.Float(
        string='Production Remaining Quantity',
        digits='Product Unit of Measure',
        compute='_compute_production_remaining_qty',
        help='Remaining quantity to produce (product_uom_qty - qty_producing)'
    )

    production_uom_id = fields.Many2one(
        'uom.uom',
        string='Production UOM',
        related='production_id.product_uom_id',
        readonly=True
    )

    move_ids = fields.Many2many(
        'stock.move',
        string='Available Components',
        readonly=True
    )

    component_line_ids = fields.One2many(
        'shop.floor.production.component.line',
        'picker_id',
        string='Components to Pick'
    )

    @api.depends('production_id.product_uom_qty', 'production_id.qty_producing')
    def _compute_production_remaining_qty(self):
        """Calculate remaining quantity to produce"""
        for record in self:
            if record.production_id:
                record.production_remaining_qty = record.production_id.product_uom_qty - record.production_id.qty_producing
            else:
                record.production_remaining_qty = 0.0

    @api.depends('component_line_ids.available_quantity', 'component_line_ids.bom_line_product_qty')
    def _compute_max_possible_qty(self):
        """Calculate maximum possible production quantity based on available components"""
        for record in self:
            if not record.component_line_ids:
                record.max_possible_qty = 0.0
                continue

            # Calculate max quantity for each component line
            max_quantities = []
            for line in record.component_line_ids:
                if line.bom_line_product_qty > 0:
                    max_qty_for_component = line.available_quantity / line.bom_line_product_qty
                    max_quantities.append(max_qty_for_component)

            # Maximum possible production is limited by the most constraining component
            max_possible_qty = min(max_quantities) if max_quantities else 0
            record.max_possible_qty = max_possible_qty if max_possible_qty > 0 else 0.0

    @api.depends('max_possible_qty', 'production_remaining_qty')
    def _compute_max_remaining_qty(self):
        """Calculate maximum remaining quantity considering both available stock and remaining production needs"""
        for record in self:
            # Use minimum of what's available and what's still needed
            record.max_remaining_qty = min(record.max_possible_qty, record.production_remaining_qty)

    @api.onchange('planned_production_qty')
    def _onchange_planned_production_qty(self):
        """Auto-calculate component quantities based on planned production"""
        if self.planned_production_qty >= 0:
            for line in self.component_line_ids:
                if line.bom_line_product_qty > 0:
                    required_qty = min(self.planned_production_qty * line.bom_line_product_qty, line.quantity_required)
                    # Set quantity to pick as min(required_qty, available_qty)
                    qty_to_pick = min(required_qty, line.available_quantity)
                    line.quantity_to_pick = qty_to_pick if qty_to_pick > 0 else 0

    def action_maximize_production(self):
        """Set planned quantity to maximum possible and update component lines"""
        self.ensure_one()

        # Debug: Check component lines availability


        # Check if component lines exist but have empty product_id (form data not saved)
        empty_product_lines = self.component_line_ids.filtered(lambda l: not l.product_id)
        if empty_product_lines or not self.component_line_ids:
             self._regenerate_component_lines()



        # If still empty, show error
        if not self.component_line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Components'),
                    'message': _('No components found to calculate maximum production quantity.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Calculate maximum possible quantity
        max_quantities = []
        for line in self.component_line_ids:
            if line.bom_line_product_qty > 0 and line.product_id:
                max_qty_for_component = line.available_quantity / line.bom_line_product_qty
                max_quantities.append(max_qty_for_component)


        # If no valid lines, calculate directly from production BoM
        if not max_quantities and self.production_id and self.production_id.bom_id:

            max_quantities = self._calculate_max_from_bom()

        max_possible_qty = min(max_quantities) if max_quantities else 0.0

        # Calculate remaining quantity needed (product_uom_qty - qty_producing)
        production_remaining_qty = 0.0
        if self.production_id:
            production_remaining_qty = self.production_id.product_uom_qty - self.production_id.qty_producing

        # Use minimum of available stock capacity and remaining production needs
        max_remaining_qty = min(max_possible_qty, production_remaining_qty)

        # Update planned quantity and component lines
        self.planned_production_qty = max_remaining_qty if max_remaining_qty > 0 else 0

        # Update component quantities - if we have regenerated lines, use them
        component_lines = self.component_line_ids
        if not component_lines and max_remaining_qty > 0:
            # If we calculated from BoM but don't have lines, regenerate them now with proper quantities

            component_lines = self._regenerate_component_lines()

        # Update component quantities
        for line in component_lines:
            if line.bom_line_product_qty > 0 and line.product_id:
                required_qty = min(max_remaining_qty * line.bom_line_product_qty, line.quantity_required)
                line.quantity_to_pick = min(required_qty, line.available_quantity)

        # Return action to reload the form with updated values
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pick Components'),
            'res_model': 'shop.floor.production.component.picker',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.production_id.id,
            },
            'res_id': self.id
        }

    def _regenerate_component_lines(self):
        """Regenerate component lines from production BoM if they're missing"""
        if not self.production_id:
            return

        production = self.production_id
        bom = production.bom_id


        if not bom:
            return

        # Clear existing lines first
        if self.component_line_ids:

            self.component_line_ids.unlink()

        # Get components for this production, excluding setsco products and pale components
        component_moves = production.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and
                      m.product_uom_qty > 0 and
                      not m.product_id.is_setsco_label and
                      not m.product_id.take_in_pale
        )


        # Create lines for each component with BoM quantities
        component_line_model = self.env['shop.floor.production.component.line']
        created_lines = []

        for move in component_moves:

            bom_qty_per_unit = max(move.product_uom_qty  / production.product_uom_qty , 0)
            _logger.warning(move.product_id.name)
            _logger.warning(bom_qty_per_unit)


            # Calculate remaining quantity (total required - already consumed)
            remaining_qty = move.product_uom_qty - move.quantity - move.actual_requested_qty


            # Only add components that still have remaining quantity to pick, excluding pale components
            if remaining_qty > 0 and not move.product_id.take_in_pale:
                line_vals = {
                    'picker_id': self.id,
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'workorder_id': move.workorder_id.id if move.workorder_id else False,
                    'available_quantity': move.product_id.qty_available,
                    'quantity_to_pick': 0.0,  # Will be calculated by maximize
                    'bom_line_product_qty': bom_qty_per_unit,
                    'uom_id': move.product_uom.id,
                }

                # Create the line directly
                line = component_line_model.create(line_vals)
                created_lines.append(line)


        # Refresh the relation
        self._invalidate_cache(['component_line_ids'])

        return created_lines

    def _calculate_max_from_bom(self):
        """Calculate maximum production quantities directly from BoM and available stock"""
        max_quantities = []

        if not self.production_id or not self.production_id.bom_id:
            return max_quantities

        bom = self.production_id.bom_id
        production = self.production_id

        component_moves = production.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and
                      m.product_uom_qty > 0 and
                      not m.product_id.is_setsco_label and
                      not m.product_id.take_in_pale
        )

        for move in component_moves:
            if move.product_id.is_setsco_label or move.product_id.take_in_pale:
                continue

            # Calculate quantity needed per unit of production
            bom_qty_per_unit = max(move.product_uom_qty / production.product_uom_qty, 0)
            available_qty = move.product_id.qty_available if move.product_id.is_storable else self.production_remaining_qty

            if bom_qty_per_unit > 0:
                max_qty_for_component = available_qty / bom_qty_per_unit
                max_quantities.append(max_qty_for_component)

        return max_quantities

    @api.model
    def get_max_production_qty(self, component_data):
        """Calculate maximum production quantity from component data
        This method can be called with fresh component data from the frontend"""
        max_quantities = []
        for comp_data in component_data:
            available_qty = comp_data.get('available_quantity', 0)
            bom_qty_per_unit = comp_data.get('bom_line_product_qty', 0)
            if bom_qty_per_unit > 0:
                max_qty_for_component = available_qty / bom_qty_per_unit
                max_quantities.append(max_qty_for_component)

        return min(max_quantities) if max_quantities else 0.0

    def action_request_extra_component(self):
        """Open a wizard to request extra components outside the BoM."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request Extra Component'),
            'res_model': 'mrp.production.extra.component.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.production_id.id,
            },
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Handle both 'production_id' and 'default_production_id' context keys
        production_id = None
        if 'production_id' in self.env.context:
            production_id = self.env.context['production_id']
        elif 'default_production_id' in self.env.context:
            production_id = self.env.context['default_production_id']

        if production_id:
            production = self.env['mrp.production'].browse(production_id)

            # Set default planned quantity to remaining quantity needed
            remaining_qty = production.product_uom_qty - production.qty_producing
            res['planned_production_qty'] = 0


            # Get components for this production, excluding setsco products and pale components
            component_moves = production.move_raw_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and
                          m.product_uom_qty > 0 and
                          not m.product_id.is_setsco_label and
                          not m.product_id.take_in_pale
            )

            if component_moves:
                res['move_ids'] = [(6, 0, component_moves.ids)]

                # Create lines for each component with BoM quantities
                line_vals = []
                for move in component_moves:

                    if move.move_orig_ids.picking_type_id.code == 'mrp_operation':
                        continue
                    # Find corresponding BoM line to get quantity per unit
                    bom_qty_per_unit = max(move.product_uom_qty / production.product_uom_qty, 0)



                    # Calculate remaining quantity (total required - already consumed)
                    remaining_qty = move.product_uom_qty  - move.actual_requested_qty

                    # Only add components that still have remaining quantity to pick, excluding pale components
                    if remaining_qty > 0 and not move.product_id.take_in_pale and move.product_id.id != production.product_id.id:
                        line_vals.append((0, 0, {
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'workorder_id': move.workorder_id.id if move.workorder_id else False,
                            'available_quantity': move.product_id.qty_available if move.product_id.is_storable else remaining_qty,
                            'forecast_quantity': move.forecast_qty,
                            'quantity_required': remaining_qty,
                            'quantity_to_pick': 0.0,  # Will be calculated by onchange
                            'bom_line_product_qty': bom_qty_per_unit,
                            'uom_id': move.product_uom.id,
                        }))
                res['component_line_ids'] = line_vals

        return res

    def action_pick_components(self):
        """Confirm the extra component request and create/update picking"""
        self.ensure_one()

        for rec in self.component_line_ids:
            # Skip pale components - they should not be in transfer notes
            if rec.product_id.take_in_pale:
                _logger.warning(f"Skipping pale component {rec.product_id.name} from transfer note creation")
                continue
                
            warehouse = self.production_id.picking_type_id.warehouse_id
            if not warehouse or not warehouse.pbm_type_id:
                raise UserError(_('No Pick Components operation type (pbm_type_id) configured for warehouse.'))

            # Find existing picking for this production
            existing_picking = self.production_id.picking_ids.filtered(
                lambda p: p.picking_type_id.id == warehouse.pbm_type_id.id and p.state not in ('done', 'cancel')
            )

            if existing_picking:
                # Update existing picking
                picking = existing_picking[0]

                # Check if move already exists for this product
                existing_move = picking.move_ids.filtered(
                    lambda m: m.product_id.id == rec.product_id.id and
                              (not rec.workorder_id or m.workorder_id.id == rec.workorder_id.id)
                )

                if existing_move:
                    # Update existing move
                    move = existing_move[0]
                    move.quantity_requested = move.quantity_requested + rec.quantity_to_pick
                    rec.move_id = move.id
                else:
                    # Create new move in existing picking
                    move_vals = {
                        'name': f"Pick {rec.product_id.display_name} for {self.production_id.name}",
                        'product_id': rec.product_id.id,
                        'product_uom_qty': rec.quantity_to_pick,
                        'product_uom': rec.uom_id.id,
                        'picking_id': picking.id,
                        'location_id': warehouse.pbm_type_id.default_location_src_id.id,
                        'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
                        'origin': self.production_id.name,
                        'reference': self.production_id.name,
                        'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
                        'state': 'draft',
                        'workorder_id': rec.workorder_id.id if rec.workorder_id else False,
                        'quantity_requested': rec.quantity_to_pick,
                        'move_raw_id': rec.move_raw_id.id if rec.move_raw_id else False,
                    }
                    move = self.env['stock.move'].create(move_vals)
                    
                    # Auto-assign lot if product requires tracking and doesn't need manual selection
                    if (rec.product_id.tracking in ['lot', 'serial'] and 
                        not rec.product_id.manual_lot_reservation):
                        self._auto_assign_lot_to_move(move, rec.product_id)

                picking.action_confirm()
                picking.action_assign()
            else:
                # Create new picking for components
                picking_vals = {
                    'picking_type_id': warehouse.pbm_type_id.id,
                    'location_id': warehouse.pbm_type_id.default_location_src_id.id,
                    'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
                    'origin': f'{self.production_id.name} (Pick Components)',
                    'partner_id': False,
                    'move_type': 'direct',
                    'state': 'assigned',  # Set to ready since quantities are being requested
                    'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
                    'mrp_production_id': self.production_id.id,  # Link to MO
                }
                picking = rec.env['stock.picking'].create(picking_vals)

                move_vals = {
                    'name': f"Pick {rec.product_id.display_name} for {self.production_id.name}",
                    'product_id': rec.product_id.id,
                    'product_uom_qty': rec.quantity_to_pick,
                    'product_uom': rec.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': warehouse.pbm_type_id.default_location_src_id.id,
                    'location_dest_id': warehouse.pbm_type_id.default_location_dest_id.id,
                    'origin': self.production_id.name,
                    'reference': self.production_id.name,
                    'group_id': self.production_id.procurement_group_id.id if self.production_id.procurement_group_id else False,
                    'state': 'draft',
                    'workorder_id': rec.workorder_id.id if rec.workorder_id else False,
                    'quantity_requested': rec.quantity_to_pick,
                    'move_raw_id': rec.move_raw_id.id if rec.move_raw_id else False,
                }
                move = rec.env['stock.move'].create(move_vals)
                
                # Auto-assign lot if product requires tracking and doesn't need manual selection
                if (rec.product_id.tracking in ['lot', 'serial'] and 
                    not rec.product_id.manual_lot_reservation):
                    self._auto_assign_lot_to_move(move, rec.product_id)

                # Confirm and assign the new picking
                picking.action_confirm()
                picking.action_assign()


            lines_to_pick = self.component_line_ids.filtered(lambda l: l.quantity_to_pick > 0)
            self._send_component_pick_notifications(picking, lines_to_pick)

            # To recalculate that the source requested qty
            self.production_id.recalculate_source_requested_qty()
            # Update picking state based on requested quantities
            picking._update_pick_component_state()


    def _send_component_pick_notifications(self, picking, component_lines):
        """Send notifications to configured users about component picking creation"""
        # Get configured users from company settings
        company = self.env.company
        users_to_notify = company.shop_floor_component_pick_notify_user_ids

        if not users_to_notify:
            _logger.info("[Shop Floor] No users configured for component pick notifications in company %s",
                         company.name)
            return

        try:
            # Prepare notification message
            component_names = ', '.join(component_lines.mapped('product_id.name'))
            total_components = len(component_lines)

            notification_title = _('Component Picking Created')
            notification_body = _(
                'Component picking %(picking_name)s has been created for manufacturing order %(mo_name)s.\n\n'
                'Components (%(total)d items):\n%(components)s\n\n'
                'Please process this picking in the Inventory module.'
            ) % {
                                    'picking_name': picking.name,
                                    'mo_name': self.production_id.name,
                                    'total': total_components,
                                    'components': component_names
                                }

            # Send notification to each configured user
            for user in users_to_notify:
                if user.active:  # Only notify active users
                    self.env['mail.message'].create({
                        'subject': notification_title,
                        'body': notification_body,
                        'model': 'stock.picking',
                        'res_id': picking.id,
                        'message_type': 'notification',
                        'partner_ids': [(4, user.partner_id.id)] if user.partner_id else [],
                        'notification_ids': [(0, 0, {
                            'res_partner_id': user.partner_id.id,
                            'notification_type': 'inbox',
                            'is_read': False,
                        })] if user.partner_id else [],
                    })

            _logger.info(
                f"[Shop Floor] Sent component pick notifications to {len(users_to_notify)} users for picking {picking.name}")

        except Exception as e:
            _logger.error(f"[Shop Floor] Error sending component pick notifications: {e}")
            # Don't fail the picking creation if notification fails

    def _auto_assign_lot_to_move(self, move, product):
        """Auto-assign lot to move for products that don't require manual selection"""
        try:
            # Find available lots for this product
            available_lots = self.env['stock.lot'].search([
                ('product_id', '=', product.id),
                ('company_id', '=', self.production_id.company_id.id)
            ])
            
            if available_lots:
                # Use FIFO (First In, First Out) - oldest lot first
                lot = available_lots.sorted('create_date')[0]
                move.lot_ids = [(6, 0, [lot.id])]
                _logger.info(f"Auto-assigned lot {lot.name} to move {move.id} for product {product.name}")
        except Exception as e:
            _logger.warning(f"Failed to auto-assign lot for product {product.name}: {e}")


class ShopFloorProductionComponentLine(models.TransientModel):
    _name = 'shop.floor.production.component.line'
    _description = 'Shop Floor Production Component Line'

    picker_id = fields.Many2one(
        'shop.floor.production.component.picker',
        string='Picker',
        required=True,
        ondelete='cascade'
    )

    move_id = fields.Many2one(
        'stock.move',
        string='Source Stock Move',
        readonly=True,
        help='Original stock move from production for reference'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=False
    )

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        readonly=False,
        help='Work order that uses this component'
    )

    quantity_to_pick = fields.Float(
        string='Quantity to Pick',
        digits='Product Unit of Measure',
        required=True
    )

    quantity_required = fields.Float(
        string='Remaining Quantity Required',
        digits='Product Unit of Measure',
        readonly=False
    )

    available_quantity = fields.Float(
        string='Available Quantity',
        digits='Product Unit of Measure',
        readonly=False
    )
    forecast_quantity = fields.Float(
        string='Forecast Quantity',
        digits='Product Unit of Measure',
        readonly=False
    )
    move_raw_id = fields.Many2one('stock.move', string="initial stock move")

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        readonly=False
    )

    total_requested_qty = fields.Float(
        string='Total Requested Quantity',
        readonly=True,
        default=0.0,
        digits='Product Unit of Measure',
        help='Cumulative quantity requested for this component line.'
    )

    bom_line_product_qty = fields.Float(
        string='BoM Quantity per Unit',
        digits='Product Unit of Measure',
        readonly=False,
        default=0.0,
        help='Quantity of this component needed per unit of production'
    )

    quantity_deficit = fields.Float(
        string='Quantity Deficit',
        compute='_compute_quantity_deficit',
        digits='Product Unit of Measure',
        help='Shortage quantity if required > available'
    )

    has_shortage = fields.Boolean(
        string='Has Shortage',
        compute='_compute_quantity_deficit',
        help='True if required quantity exceeds available quantity'
    )

    @api.depends('quantity_to_pick', 'available_quantity')
    def _compute_quantity_deficit(self):
        """Calculate if there's a shortage and how much"""
        for line in self:
            if line.quantity_to_pick > line.available_quantity:
                line.quantity_deficit = line.quantity_to_pick - line.available_quantity
                line.has_shortage = True
            else:
                line.quantity_deficit = 0.0
                line.has_shortage = False

    def increment_requested_qty(self, qty):
        """Increment the total requested quantity by the given amount."""
        for line in self:
            line.total_requested_qty += qty


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            """Override create to ensure readonly fields from context are saved"""
            # Handle readonly fields that might be passed through context
            if 'product_id' not in vals and 'default_product_id' in self.env.context:
                vals['product_id'] = self.env.context['default_product_id']

            if 'available_quantity' not in vals and 'default_available_quantity' in self.env.context:
                vals['available_quantity'] = self.env.context['default_available_quantity']

            if 'forecast_quantity' not in vals and 'default_forecast_quantity' in self.env.context:
                vals['forecast_quantity'] = self.env.context['default_forecast_quantity']

            if 'uom_id' not in vals and 'default_uom_id' in self.env.context:
                vals['uom_id'] = self.env.context['default_uom_id']

            if 'move_id' not in vals and 'default_move_id' in self.env.context:
                vals['move_id'] = self.env.context['default_move_id']

            if 'move_raw_id' not in vals and 'default_move_raw_id' in self.env.context:
                vals['move_raw_id'] = self.env.context['default_move_raw_id']

            if 'workorder_id' not in vals and 'default_workorder_id' in self.env.context:
                vals['workorder_id'] = self.env.context['default_workorder_id']

        return super().create(vals_list)

    def write(self, vals):
        """Override write to ensure readonly fields from context are saved"""
        # Handle readonly fields that might be passed through context
        if 'product_id' not in vals and 'default_product_id' in self.env.context:
            vals['product_id'] = self.env.context['default_product_id']

        if 'available_quantity' not in vals and 'default_available_quantity' in self.env.context:
            vals['available_quantity'] = self.env.context['default_available_quantity']

        if 'uom_id' not in vals and 'default_uom_id' in self.env.context:
            vals['uom_id'] = self.env.context['default_uom_id']

        if 'move_id' not in vals and 'default_move_id' in self.env.context:
            vals['move_id'] = self.env.context['default_move_id']

        if 'workorder_id' not in vals and 'default_workorder_id' in self.env.context:
            vals['workorder_id'] = self.env.context['default_workorder_id']

        return super().write(vals)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-select UoM when product is selected"""
        if self.product_id:
            # Set the UoM to the product's default UoM
            self.uom_id = self.product_id.uom_id.id
            self.available_quantity = self.product_id.qty_available
            self.forecast_quantity = self.product_id.virtual_available + self.quantity_required
        else:
            # Clear UoM if no product is selected
            self.available_quantity = 0
            self.uom_id = False

    @api.constrains('quantity_to_pick', 'available_quantity', 'total_requested_qty')
    def _check_quantity_to_pick(self):
        for line in self:
            if line.quantity_to_pick < 0:
                raise ValidationError(_('Quantity to pick cannot be negative.'))

    @api.onchange('quantity_to_pick', 'available_quantity', 'total_requested_qty')
    def _onchange_quantity_to_pick(self):
        for line in self:
            if (line.total_requested_qty + line.quantity_to_pick > line.available_quantity)  and line.product_id.is_storable :
                raise ValidationError(
                    _('Total requested quantity (%s) exceeds available quantity (%s) for %s. You may only request the stock when it is available in the warehouse') % (
                        line.total_requested_qty + line.quantity_to_pick,
                        line.available_quantity,
                        line.product_id.display_name
                    ))
            if (line.total_requested_qty + line.quantity_to_pick > line.quantity_required)  and line.product_id.is_storable :
                raise ValidationError(
                    _('Total requested quantity (%s) exceeds remaining quantity (%s) for %s. You may only request the stock when it is drafted in the production order') % (
                        line.total_requested_qty + line.quantity_to_pick,
                        line.quantity_required,
                        line.product_id.display_name
                    ))


