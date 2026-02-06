# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    sale_work_order_ids = fields.Many2many(
        'sale.work.order',
        'mrp_production_sale_work_order_rel',
        'production_id',
        'work_order_id',
        string='Sale Work Orders',
        readonly=True,
        copy=False,
        help='Sale work orders that triggered this manufacturing order'
    )
    
    sale_work_order_line_ids = fields.Many2many(
        'sale.work.order.line',
        'mrp_production_sale_work_order_line_rel',
        'production_id',
        'work_order_line_id',
        string='Sale Work Order Lines',
        copy=False,
        readonly=True,
        help='Sale work order lines that triggered this manufacturing order'
    )

    sale_order_ids = fields.Many2many(
        'sale.order', 
        'mrp_production_sale_order_rel', 
        'production_id', 
        'sale_order_id',
        copy=False,
        string='Related Sale Orders'
    )

    # SFP Distribution fields
    sfp_distribution_ids = fields.One2many(
        'mrp.production.sfp.distribution', 
        'production_id',
        string='SFP Distribution Plan',
        compute='_compute_sfp_distribution_ids',
        store=False
    )
    
    sfp_distribution_required = fields.Boolean(
        string='SFP Distribution Required',
        compute='_compute_sfp_distribution_required',
        store=True,
        help='True if any linked SWO lines have custom destinations'
    )
    
    sfp_distribution_count = fields.Integer(
        string='SFP Distribution Count',
        compute='_compute_sfp_distribution_count'
    )

    assigned_distribution_qty = fields.Float(string="Assigned Distribution Qty", default=0, copy=False)

    def _get_backorder_mo_vals(self):
        """Override to add sale work order relationships to backorder"""
        vals = super()._get_backorder_mo_vals()
        
        # Copy sale work order relationships to backorder
        if self.sale_work_order_ids:
            vals['sale_work_order_ids'] = [(6, 0, self.sale_work_order_ids.ids)]
        if self.sale_work_order_line_ids:
            vals['sale_work_order_line_ids'] = [(6, 0, self.sale_work_order_line_ids.ids)]
        if self.sale_order_ids:
            vals['sale_order_ids'] = [(6, 0, self.sale_order_ids.ids)]
        
        # Ensure procurement group is copied to backorder
        if self.procurement_group_id:
            vals['procurement_group_id'] = self.procurement_group_id.id
        
        return vals

    @api.depends('procurement_group_id')
    def _compute_sfp_distribution_ids(self):
        """Compute SFP distribution records from procurement group"""
        for production in self:
            if production.procurement_group_id:
                distributions = self.env['mrp.production.sfp.distribution'].search([
                    ('procurement_group_id', '=', production.procurement_group_id.id)
                ])
                production.sfp_distribution_ids = distributions
            else:
                production.sfp_distribution_ids = self.env['mrp.production.sfp.distribution']

    @api.depends('sale_work_order_line_ids', 'sale_work_order_line_ids.destination_location_id')
    def _compute_sfp_distribution_required(self):
        """Check if any linked SWO lines have custom destinations"""
        for production in self:
            production.sfp_distribution_required = True
            return


    @api.depends('sfp_distribution_ids')
    def _compute_sfp_distribution_count(self):
        """Count SFP distribution records from procurement group"""
        for production in self:
            if production.procurement_group_id:
                count = self.env['mrp.production.sfp.distribution'].search_count([
                    ('procurement_group_id', '=', production.procurement_group_id.id)
                ])
                production.sfp_distribution_count = count
            else:
                production.sfp_distribution_count = 0

    def action_confirm(self):
        """Override to create SFP distribution plan when MO is confirmed"""
        result = super().action_confirm()
        
        for production in self:
            if production.sfp_distribution_required:
                production._create_sfp_distribution_plan()
        
        return result
    
    def _create_sfp_distribution_plan(self):
        """Create SFP distribution plan based on SWO line destinations"""
        self.ensure_one()
        
        # Clear existing distributions
        self.sfp_distribution_ids.unlink()
        
        # Group SWO lines by destination location
        location_groups = {}
        total_swo_qty = 0
        
        for line in self.sale_work_order_line_ids:
            if line.destination_location_id:
                location_id = line.destination_location_id.id
                if location_id not in location_groups:
                    location_groups[location_id] = []
                location_groups[location_id].append(line)
                total_swo_qty += line.product_qty
        
        # Create distributions for SWO line destinations
        for location_id, lines in location_groups.items():
            total_qty = sum(line.qty_remaining for line in lines)
            
            self.env['mrp.production.sfp.distribution'].create({
                'production_id': self.id,
                'distribution_type': 'swo_line',
                'sale_work_order_line_id': lines[0].id,
                'location_dest_id': location_id,
                'product_id': self.product_id.id,
                'planned_qty': total_qty,
                'state': 'draft'
            })
        
        # Handle excess production
        excess_qty = self.product_qty - total_swo_qty
        if excess_qty > 0:
            # Get default SFP location from operation type
            warehouse = self.picking_type_id.warehouse_id
            if warehouse and warehouse.sam_type_id and warehouse.sam_type_id.default_location_dest_id:
                default_location = warehouse.sam_type_id.default_location_dest_id
                
                self.env['mrp.production.sfp.distribution'].create({
                    'production_id': self.id,
                    'distribution_type': 'excess',
                    'location_dest_id': default_location.id,
                    'product_id': self.product_id.id,
                    'planned_qty': excess_qty,
                    'state': 'draft'
                })

    def button_mark_done(self):
        """Override to create custom SFP transfers before marking done"""

        for production in self:
            if production.sfp_distribution_required and production.sfp_distribution_ids:
                production._create_custom_sfp_transfers()
        
        result = super().button_mark_done()

        # Update sale work order line states
        for production in self:
            if production.state == 'done':
                production.sale_work_order_line_ids._compute_state()
        
        return result
    
    def _create_custom_sfp_transfers(self):
        """Create multiple SFP transfers based on distribution plan and actual produced quantity"""
        self.ensure_one()
        # Get actual produced quantity
        produced_qty = self.qty_producing
        if produced_qty <= 0 or self.assigned_distribution_qty == produced_qty:
            return
        
        # Get all SWO line distributions sorted by SWO line ID from procurement group
        if not self.procurement_group_id:
            return
            
        swo_distributions = self.env['mrp.production.sfp.distribution'].search([
            ('procurement_group_id', '=', self.procurement_group_id.id),
            ('distribution_type', '=', 'swo_line'),
        ]).sorted(lambda d: d.sale_work_order_line_id.id)
        
        # Get excess distributions from procurement group
        excess_distributions = self.env['mrp.production.sfp.distribution'].search([
            ('procurement_group_id', '=', self.procurement_group_id.id),
            ('distribution_type', '=', 'excess'),
        ])
        
        remaining_qty = produced_qty

        # First, allocate to SWO line distributions in priority order
        for distribution in swo_distributions:
            if remaining_qty <= 0:
                break
                
            # Get the SWO line to check remaining quantity
            swo_line = distribution.sale_work_order_line_id
            swo_remaining = swo_line.qty_remaining
            
            # Calculate how much to allocate to this distribution
            # Use the minimum of: remaining production qty, SWO line remaining qty, distribution planned qty
            planned_qty = distribution.planned_qty
            allocated_qty = min(remaining_qty, swo_remaining, planned_qty)
            
            if allocated_qty > 0:
                # Update only the actual_qty, keep planned_qty unchanged
                distribution.write({
                    'actual_qty': allocated_qty + distribution.actual_qty
                })
                
                # Create the transfer
                distribution.action_create_sfp_transfer(production_id = self)
                remaining_qty -= allocated_qty
        
        # Then, allocate remaining quantity to excess distributions
        for distribution in excess_distributions:
            if remaining_qty <= 0:
                break
                
            # Calculate how much to allocate to this distribution
            planned_qty = distribution.planned_qty
            allocated_qty = min(planned_qty, remaining_qty)
            
            if allocated_qty > 0:
                # Update only the actual_qty, keep planned_qty unchanged
                distribution.write({
                    'actual_qty': allocated_qty
                })
                
                # Create the transfer
                distribution.action_create_sfp_transfer(production_id = self)
                remaining_qty -= allocated_qty
        self.assigned_distribution_qty = produced_qty
    
    def action_view_sfp_distributions(self):
        """View SFP distribution plan"""
        self.ensure_one()
        
        if not self.procurement_group_id:
            return {'type': 'ir.actions.act_window_close'}
        
        # Get distributions from procurement group
        distributions = self.env['mrp.production.sfp.distribution'].search([
            ('procurement_group_id', '=', self.procurement_group_id.id)
        ])
        
        action = self.env["ir.actions.actions"]._for_xml_id("lingjack_sale_workorder.action_mrp_production_sfp_distribution")
        
        if len(distributions) > 1:
            action['domain'] = [('id', 'in', distributions.ids)]
        elif len(distributions) == 1:
            action['views'] = [(self.env.ref('lingjack_sale_workorder.view_mrp_production_sfp_distribution_form').id, 'form')]
            action['res_id'] = distributions.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        
        return action

    def action_view_sfp_pickings(self):
        """View SFP transfer notes linked to this production order"""
        self.ensure_one()
        
        # Find SFP transfer notes linked to this production order
        sfp_pickings = self.env['stock.picking']
        
        # Try multiple approaches to find related pickings
        try:
            # Approach 1: Use mrp_production_id field (if available)
            sfp_pickings = self.env['stock.picking'].search([
                ('mrp_production_id', '=', self.id),
                ('picking_type_id.code', '=', 'internal'),
                ('state', 'in', ['draft', 'waiting', 'confirmed', 'assigned'])
            ])
        except:
            pass
        
        # Approach 2: Use procurement group (standard Odoo way)
        if not sfp_pickings and self.procurement_group_id:
            sfp_pickings = self.env['stock.picking'].search([
                ('group_id', '=', self.procurement_group_id.id),
                ('picking_type_id.code', '=', 'internal'),
                ('state', 'in', ['draft', 'waiting', 'confirmed', 'assigned']),
                ('origin', 'ilike', self.name)
            ])
        
        # Approach 3: Use move origins
        if not sfp_pickings:
            sfp_pickings = self.env['stock.picking'].search([
                ('move_ids.origin', '=', self.name),
                ('picking_type_id.code', '=', 'internal'),
                ('state', 'in', ['draft', 'waiting', 'confirmed', 'assigned'])
            ])
        
        if sfp_pickings:
            action = {
                'type': 'ir.actions.act_window',
                'name': f'SFP Transfers - {self.name}',
                'res_model': 'stock.picking',
                'view_mode': 'list,form',
                'domain': [('id', 'in', sfp_pickings.ids)],
                'context': {'default_mrp_production_id': self.id},
            }
            
            if len(sfp_pickings) == 1:
                action.update({
                    'view_mode': 'form',
                    'res_id': sfp_pickings.id,
                })
            
            return action
        else:
            return {'type': 'ir.actions.act_window_close'}

    def _split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False):
        """Override to handle sale work order relationships in split productions"""
        backorders = super()._split_productions(amounts=amounts, 
                                              cancel_remaining_qty=cancel_remaining_qty, 
                                              set_consumed_qty=set_consumed_qty)
        
        # Handle relationships for backorders
        for backorder in backorders:
            # Find all sale work orders from the origin
            origins = backorder.origin.split(',') if backorder.origin else []
            origins = [org.strip() for org in origins]

            # Find sale work orders
            sale_work_orders = self.env['sale.work.order'].search([
                ('name', 'in', origins)
            ])
            
            # Find sale work order lines
            sale_work_order_lines = self.env['sale.work.order.line'].search([
                ('work_order_id', 'in', sale_work_orders.ids),
                ('product_id', '=', backorder.product_id.id)
            ])

            # Find related sale orders
            # 1. From sale work orders
            sale_orders_from_wo = sale_work_orders.mapped('sale_order_id')
            
            # 2. From origin references (SO/2023/001 format)
            sale_order_refs = [org for org in origins if 'SO/' in org or 'S' in org]
            sale_orders_from_ref = self.env['sale.order'].search([
                ('name', 'in', sale_order_refs)
            ]) if sale_order_refs else self.env['sale.order']

            # 3. From procurement group
            sale_orders_from_group = self.env['sale.order']
            if backorder.procurement_group_id:
                sale_orders_from_group = self.env['sale.order'].search([
                    ('procurement_group_id', '=', backorder.procurement_group_id.id)
                ])

            # Combine all found sale orders
            all_sale_orders = sale_orders_from_wo | sale_orders_from_ref | sale_orders_from_group
            
            # Update the many2many fields
            if sale_work_orders:
                backorder.sale_work_order_ids = [(4, wo.id) for wo in sale_work_orders]
            if sale_work_order_lines:
                backorder.sale_work_order_line_ids = [(4, line.id) for line in sale_work_order_lines]
            if all_sale_orders:
                backorder.sale_order_ids = [(4, so.id) for so in all_sale_orders]

            # Ensure procurement group is set for SFP distribution
            if self.procurement_group_id and not backorder.procurement_group_id:
                backorder.procurement_group_id = self.procurement_group_id.id

            # Log the relationships for debugging
            _logger.info(
                'Backorder %s relationships updated: %d sale orders, %d work orders, %d work order lines',
                backorder.name,
                len(all_sale_orders),
                len(sale_work_orders),
                len(sale_work_order_lines)
            )
            
            # Update the state of work order lines if needed
            sale_work_order_lines._compute_state()
        
        return backorders
