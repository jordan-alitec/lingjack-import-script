# -*- coding: utf-8 -*-

from itertools import filterfalse
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from datetime import datetime
import logging
import re
from collections import defaultdict
_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _order = 'sequence, id'

    fsm_month = fields.Char(string='FSM Month')
    last_updated_date = fields.Date(string='Last Updated Date')
    special_id = fields.Text(string='Special ID')
    bus_quantities = fields.Json(string='Bus Quantities', default=dict, help='JSON mapping of bus special_id to quantity: {bus_name: qty}')
    bus_quantities_by_task = fields.Json(
        string='Bus Quantities (By Task)',
        default=dict,
        help="Per-subtask bus quantities. Format: {task_id: {bus_name: qty}}. Used to split deliveries by subtask when the SO line is grouped.",
    )
    product_uom_qty_by_task = fields.Json(
        string='Quantity By Task (Type Name)',
        default=dict,
        help="Per-subtask quantities for type_name-only lines (no special_id). Format: {task_id: qty}. Used to split deliveries by subtask when same product+type_name is grouped into one SO line.",
    )

    # -------------------------------------------------------------------------
    # Stock picking split: 1 subtask (task_id) = 1 delivery order
    #
    # Your tasks/subtasks share ONE sale order (see `project.task._fsm_ensure_sale_order`).
    # Odoo normally creates ONE procurement group per sale order, which merges all
    # stock moves into the same outgoing picking. By assigning a dedicated
    # procurement group per task_id, Odoo will naturally create one picking per
    # task/subtask when the sale order is confirmed.
    # -------------------------------------------------------------------------
    procurement_group_id = fields.Many2one(
        'procurement.group',
        string='Procurement Group (Task)',
        copy=False,
    )

    def _get_procurement_group(self):
        """Return procurement group to use for this line.

        For FSM lines linked to a task/subtask, we purposely avoid using the sale
        order's shared procurement group so we can generate one delivery per task.
        """
        self.ensure_one()
        # If we already assigned a group for this task, reuse it.
        if self.procurement_group_id:
            return self.procurement_group_id
        # For non-task lines, keep standard behavior (group by sale order).
        if not self.task_id:
            return super()._get_procurement_group()
        # For task-linked lines with no assigned group yet, force creation.
        return False

    def _get_procurement_group_key(self):
        """Key used to regroup lines into the same procurement group.

        We group by (sale order, task_id). This yields 1 group => 1 picking per subtask.
        """
        self.ensure_one()
        # Use a higher priority than common split modules (e.g. split-by-date)
        # so "1 subtask = 1 group" wins.
        return 80, (self.order_id.id, self.task_id.id or 0)

    def _find_or_reuse_orphaned_procurement_group(self, order_id, task_id):
        """
        Find an existing procurement group for the sale order that has no task_id
        (orphaned group) and can be reused for the given task.
        
        This handles the case where:
        1. SO is confirmed → creates DO without task
        2. Task is created and linked to SO
        3. Products are added via add_normal_product/add_control_tag_to_product
        4. Instead of creating a new DO, reuse the existing orphaned DO
        
        :param order_id: sale.order record
        :param task_id: task ID to assign to the group
        :return: procurement.group record or False
        """
        if not task_id:
            return False
        
        # Find pickings for this sale order that:
        # - Are not done/cancelled
        # - Belong to a procurement group with no task_id (orphaned)
        orphaned_pickings = self.env['stock.picking'].search([
            ('sale_id', '=', order_id.id),
            ('state', 'not in', ['done', 'cancel']),
            ('group_id.task_id', '=', False),  # Group has no task
        ], limit=1)
        
        if orphaned_pickings:
            group = orphaned_pickings.group_id
            # Found an orphaned group with active pickings for this SO
            # Assign the task to it and update the name to match the pattern
            group.write({
                'task_id': task_id,
                'name': f"{order_id.name}/TASK/{task_id}",  # Update name to match pattern
            })
            return group
        
        return False

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Launch procurements split by task/subtask.

        This is adapted from the standard/OCA approach: create/run procurements
        using our per-task procurement groups, then call super() with
        `previous_product_uom_qty` filled to avoid duplicate procurements.
        """
        if self._context.get('skip_procurement'):
            return True

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        procurements = []
        groups = {}
        control_tag_groups_by_task = {}

        if not previous_product_uom_qty:
            previous_product_uom_qty = {}

        for line in self:
            line = line.with_company(line.company_id)
            if line.state != 'sale' or line.product_id.type not in ('consu', 'product'):
                continue

            # Special case (bus quantities): keep ONE SOL but create procurements per subtask.
            # Used when bus entries from multiple subtasks are grouped into one line.
            if isinstance(getattr(line, 'bus_quantities_by_task', None), dict) and line.bus_quantities_by_task:
                # Compute desired qty per subtask from JSON: {task_id: {bus: qty}}
                desired_by_task = {}
                for k, v in (line.bus_quantities_by_task or {}).items():
                    try:
                        task_id = int(k)
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(v, dict):
                        continue
                    desired_by_task[task_id] = sum((qty or 0.0) for qty in v.values())

                # Only relevant if we have at least one task bucket
                if desired_by_task:
                    demanded_qty_by_task = defaultdict(float)
                    for mv in line.move_ids.filtered(lambda m: m.state != 'cancel'):
                        mv_task = getattr(getattr(mv, 'group_id', False), 'task_id', False)
                        mv_task_id = mv_task.id if mv_task else 0
                        demanded_qty_by_task[mv_task_id] += mv.product_uom_qty

                    for task_id, desired_qty in desired_by_task.items():
                        already_demanded = demanded_qty_by_task.get(task_id, 0.0)
                        delta_qty = desired_qty - already_demanded
                        if float_compare(delta_qty, 0.0, precision_digits=precision) <= 0:
                            continue

                        group_key = 80, (line.order_id.id, task_id)
                        group = groups.get(group_key)
                        if not group:
                            group_name = f"{line.order_id.name}/TASK/{task_id}"
                            group = self.env['procurement.group'].search([
                                ('name', '=', group_name),
                                ('task_id', '=', task_id),
                            ], limit=1)
                            if not group:
                                # Try to reuse an orphaned group (DO without task)
                                group = line._find_or_reuse_orphaned_procurement_group(line.order_id, task_id)
                                if not group:
                                    vals = line._prepare_procurement_group_vals()
                                    vals.update({'task_id': task_id, 'name': group_name})
                                    group = self.env['procurement.group'].create(vals)
                        groups[group_key] = group

                        values = line._prepare_procurement_values(group_id=group)
                        product_qty, procurement_uom = line.product_uom._adjust_uom_quantities(delta_qty, line.product_id.uom_id)
                        procurements.append(
                            self.env['procurement.group'].Procurement(
                                line.product_id,
                                product_qty,
                                procurement_uom,
                                line.order_id.partner_shipping_id.property_stock_customer,
                                line.display_name,
                                line.order_id.name,
                                line.order_id.company_id,
                                values,
                            )
                        )

                    previous_product_uom_qty[line.id] = line.product_uom_qty
                    continue

            # Special case (type_name-only, no special_id): keep ONE SOL but create procurements per subtask.
            # When same product+type_name is grouped from multiple subtasks, split DOs by task.
            if (
                line.type_name
                and not (isinstance(getattr(line, 'bus_quantities_by_task', None), dict) and line.bus_quantities_by_task)
                and isinstance(getattr(line, 'product_uom_qty_by_task', None), dict)
                and line.product_uom_qty_by_task
            ):
                desired_by_task = {}
                for k, v in (line.product_uom_qty_by_task or {}).items():
                    try:
                        task_id = int(k)
                    except (TypeError, ValueError):
                        continue
                    if v is None:
                        continue
                    try:
                        desired_by_task[task_id] = float(v)
                    except (TypeError, ValueError):
                        continue
                if desired_by_task:
                    demanded_qty_by_task = defaultdict(float)
                    for mv in line.move_ids.filtered(lambda m: m.state != 'cancel'):
                        mv_task = getattr(getattr(mv, 'group_id', False), 'task_id', False)
                        mv_task_id = mv_task.id if mv_task else 0
                        demanded_qty_by_task[mv_task_id] += mv.product_uom_qty
                    for task_id, desired_qty in desired_by_task.items():
                        already_demanded = demanded_qty_by_task.get(task_id, 0.0)
                        delta_qty = desired_qty - already_demanded
                        if float_compare(delta_qty, 0.0, precision_digits=precision) <= 0:
                            continue
                        group_key = 80, (line.order_id.id, task_id)
                        group = groups.get(group_key)
                        if not group:
                            group_name = f"{line.order_id.name}/TASK/{task_id}"
                            group = self.env['procurement.group'].search([
                                ('name', '=', group_name),
                                ('task_id', '=', task_id),
                            ], limit=1)
                            if not group:
                                group = line._find_or_reuse_orphaned_procurement_group(line.order_id, task_id)
                                if not group:
                                    vals = line._prepare_procurement_group_vals()
                                    vals.update({'task_id': task_id, 'name': group_name})
                                    group = self.env['procurement.group'].create(vals)
                        groups[group_key] = group
                        values = line._prepare_procurement_values(group_id=group)
                        product_qty, procurement_uom = line.product_uom._adjust_uom_quantities(delta_qty, line.product_id.uom_id)
                        procurements.append(
                            self.env['procurement.group'].Procurement(
                                line.product_id,
                                product_qty,
                                procurement_uom,
                                line.order_id.partner_shipping_id.property_stock_customer,
                                line.display_name,
                                line.order_id.name,
                                line.order_id.company_id,
                                values,
                            )
                        )
                    previous_product_uom_qty[line.id] = line.product_uom_qty
                    continue

            # Special case: keep ONE control-tag SOL but create procurements per subtask.
            # `control_tag_ids_json` supports:
            # - Legacy: {task_id: lot_id or [lot_ids...]}
            # - Refined: {task_id: {worksheet_line_id: lot_id}}
            control_tag_product = line.env.company.fsm_control_tag_product_id
            if control_tag_product and line.product_id.id == control_tag_product.id and isinstance(line.control_tag_ids_json, dict) and line.control_tag_ids_json:
                # Seed existing groups from other lines so we can reuse the same picking per subtask.
                for order_line in line.order_id.order_line:
                    g_id = order_line.procurement_group_id or False
                    if g_id:
                        groups[order_line._get_procurement_group_key()] = g_id

                # Compute desired qty per subtask from JSON
                task_to_lots = defaultdict(list)
                for k, v in (line.control_tag_ids_json or {}).items():
                    try:
                        task_id = int(k)
                    except (TypeError, ValueError):
                        continue
                    if not v:
                        continue
                    if isinstance(v, dict):
                        task_to_lots[task_id].extend([x for x in v.values() if x])
                    elif isinstance(v, list):
                        task_to_lots[task_id].extend([x for x in v if x])
                    else:
                        task_to_lots[task_id].append(v)

                # Compute already-demanded quantities per subtask from existing moves
                # so we only procure the delta when new tags are added.
                demanded_qty_by_task = defaultdict(float)
                for mv in line.move_ids.filtered(lambda m: m.state != 'cancel'):
                    mv_task = getattr(getattr(mv, 'group_id', False), 'task_id', False)
                    mv_task_id = mv_task.id if mv_task else 0
                    demanded_qty_by_task[mv_task_id] += mv.product_uom_qty

                for task_id, lots in task_to_lots.items():
                    desired_qty = len(set(lots))
                    already_demanded = demanded_qty_by_task.get(task_id, 0.0)
                    delta_qty = desired_qty - already_demanded
                    # If we already have enough demand for this subtask, do not create new procurements.
                    if float_compare(delta_qty, 0.0, precision_digits=precision) <= 0:
                        continue

                    # Create/reuse a procurement group dedicated to this subtask
                    group_key = 80, (line.order_id.id, task_id)
                    group = groups.get(group_key) or control_tag_groups_by_task.get(task_id)
                    if not group:
                        # Deterministic name so we can reliably find/reuse it across calls.
                        # This avoids creating multiple groups/DOs for the same subtask when other
                        # modules alter procurement group naming (e.g. date-based suffixes).
                        group_name = f"{line.order_id.name}/TASK/{task_id}"
                        group = self.env['procurement.group'].search([
                            ('name', '=', group_name),
                            ('task_id', '=', task_id),
                        ], limit=1)
                        if not group:
                            # Try to reuse an orphaned group (DO without task)
                            group = line._find_or_reuse_orphaned_procurement_group(line.order_id, task_id)
                            if not group:
                                vals = line._prepare_procurement_group_vals()
                                vals.update({'task_id': task_id})
                                vals['name'] = group_name
                                group = self.env['procurement.group'].create(vals)
                        else:
                            updated_vals = {}
                            if group.partner_id != line.order_id.partner_shipping_id:
                                updated_vals['partner_id'] = line.order_id.partner_shipping_id.id
                            if group.move_type != line.order_id.picking_policy:
                                updated_vals['move_type'] = line.order_id.picking_policy
                            if updated_vals:
                                group.write(updated_vals)
                        control_tag_groups_by_task[task_id] = group
                    # Make sure subsequent order lines reuse the same group.
                    groups[group_key] = group

                    values = line._prepare_procurement_values(group_id=group)
                    product_qty, procurement_uom = line.product_uom._adjust_uom_quantities(delta_qty, line.product_id.uom_id)
                    procurements.append(
                        self.env['procurement.group'].Procurement(
                            line.product_id,
                            product_qty,
                            procurement_uom,
                            line.order_id.partner_shipping_id.property_stock_customer,
                            line.display_name,
                            line.order_id.name,
                            line.order_id.company_id,
                            values,
                        )
                    )

                # Mark line as fully procured for this launch to prevent super from duplicating it.
                previous_product_uom_qty[line.id] = line.product_uom_qty
                continue

            qty = line._get_qty_procurement(previous_product_uom_qty) or 0.0
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) == 0:
                continue

            group_id = line._get_procurement_group()

            # Reuse already-created groups for the same (order, task) key.
            for order_line in line.order_id.order_line:
                g_id = order_line.procurement_group_id or False
                if g_id:
                    groups[order_line._get_procurement_group_key()] = g_id
            if not group_id:
                group_id = groups.get(line._get_procurement_group_key())

            if not group_id:
                vals = line._prepare_procurement_group_vals()
                # Tag procurement group with task/subtask for downstream lot assignment & DO splitting.
                # IMPORTANT: When adding products AFTER SO is confirmed, we must reuse the existing
                # group for that subtask, otherwise Odoo creates a new DO per product.
                if line.task_id:
                    vals['task_id'] = line.task_id.id
                    group_name = f"{line.order_id.name}/TASK/{line.task_id.id}"
                    # Search existing group first (stable name per SO+task).
                    group_id = self.env['procurement.group'].search([
                        ('name', '=', group_name),
                        ('task_id', '=', line.task_id.id),
                    ], limit=1)
                    if not group_id:
                        # Try to reuse an orphaned group (DO without task)
                        group_id = line._find_or_reuse_orphaned_procurement_group(line.order_id, line.task_id.id)
                        if not group_id:
                            vals['name'] = group_name
                            group_id = self.env['procurement.group'].create(vals)
                else:
                    group_id = self.env['procurement.group'].create(vals)
            else:
                # Keep group values aligned with order changes.
                updated_vals = {}
                if group_id.partner_id != line.order_id.partner_shipping_id:
                    updated_vals['partner_id'] = line.order_id.partner_shipping_id.id
                if group_id.move_type != line.order_id.picking_policy:
                    updated_vals['move_type'] = line.order_id.picking_policy
                if line.task_id and not getattr(group_id, 'task_id', False):
                    updated_vals['task_id'] = line.task_id.id
                if updated_vals:
                    group_id.write(updated_vals)

            line.procurement_group_id = group_id

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.product_uom_qty - qty

            line_uom = line.product_uom
            quant_uom = line.product_id.uom_id
            product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)

            procurements.append(
                self.env['procurement.group'].Procurement(
                    line.product_id,
                    product_qty,
                    procurement_uom,
                    line.order_id.partner_shipping_id.property_stock_customer,
                    line.display_name,
                    line.order_id.name,
                    line.order_id.company_id,
                    values,
                )
            )

            # Store procured quantity to avoid duplicated procurements downstream.
            previous_product_uom_qty[line.id] = line.product_uom_qty

        if procurements:
            self.env['procurement.group'].run(procurements)

        # Ensure pickings are confirmed so reservations/scheduler can proceed.
        orders = self.mapped('order_id')
        for order in orders:
            pickings_to_confirm = order.picking_ids.filtered(lambda p: p.state not in ['cancel', 'done'])
            if pickings_to_confirm:
                pickings_to_confirm.action_confirm()

        # Update move descriptions for bus quantities (per subtask)
        for line in self:
            if isinstance(getattr(line, 'bus_quantities_by_task', None), dict) and line.bus_quantities_by_task:
                line._update_move_descriptions_from_bus_quantities()

        return super(
            SaleOrderLine, self.with_context(sale_split_by_task=True)
        )._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
    
    #################################################################################
    # Control tag section
    #################################################################################
    # Trying to use this if and only if control tag product is used
    control_tag_ids = fields.Many2many(
        'stock.lot',
        'sale_order_line_control_tag_rel',
        'sale_line_id',
        'lot_id',
        string='Control Tag Lots'
    )
    control_tag_ids_json = fields.Json(
        string='Control Tag Lots (JSON)',
        help='JSON mapping of record_id to lot_id: {record_id: lot_id}. Used to track and replace previous lot_id when record_id is updated.'
    )
    worksheet_linked_ids = fields.Json(string='Worksheet Linked ID')
    type_name = fields.Char(string='Type Name', help='Type identifier for grouping similar product lines')
    
    @api.constrains('type_name')
    def _check_type_name(self):
        for line in self:
            if line.type_name:
                line.name = f"{line.product_id.get_product_multiline_description_sale()}\n {line.type_name}"
        return



    # override to allow deletion of delivery line in a confirmed order
    def _check_line_unlink(self):
        undeletable_lines = super()._check_line_unlink()
        return undeletable_lines.filtered(lambda line: not line.order_id.is_service_type)


    @api.depends('product_id', 'linked_line_id', 'linked_line_ids', 'control_tag_ids_json')
    def _compute_name(self):
        '''
        This function is to inherit the old function and add more dependancies
        '''
        return super()._compute_name()

    def change_unit_price(self):
        '''
        Pop up a wizard that allow user to fill in the unit price, default will be the line.price_unit,
        '''
        self.ensure_one()
        
        # Check if the sale order is locked
        if self.order_id.locked:
            raise UserError(_('Cannot change unit price on a locked sale order.'))
        
        # Create wizard context
        wizard_context = {
            'default_sale_order_line_id': self.id,
            'default_price_unit': self.price_unit,
        }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Change Unit Price'),
            'res_model': 'sale.order.line.change.unit.price.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': wizard_context,
        }



    def _extra_description_sale_line(self):
        """
        When control_tag_ids_json changes, update the description of the sale order line
        """

        res = super()._extra_description_sale_line() or ""

        if self.control_tag_ids_json:
            control_tag_ids = []
            for v in (self.control_tag_ids_json or {}).values():
                if not v:
                    continue
                if isinstance(v, dict):
                    control_tag_ids.extend([x for x in v.values() if x])
                elif isinstance(v, list):
                    control_tag_ids.extend([x for x in v if x])
                else:
                    control_tag_ids.append(v)

            lots = self.env['stock.lot'].browse(control_tag_ids)
            lot_names = sorted(lots.mapped('name'))

            if lot_names:
                res += "\nTag No: " + self._format_lot_ranges(lot_names)

        return res 


    def _format_lot_ranges(self, lots):
        if not lots:
            return ''

        pattern = re.compile(r'^(.*?)-(\d+)$')
        groups = defaultdict(list)

        # Split prefix and number
        for lot in lots:
            match = pattern.match(lot)
            if match:
                prefix, num = match.groups()
                groups[prefix].append((int(num), lot))
            else:
                # Non-matching lots (fallback)
                groups[lot].append((None, lot))

        results = []

        for prefix, values in groups.items():
            # Separate numeric and non-numeric
            numeric = sorted(v for v in values if v[0] is not None)
            text_only = [v[1] for v in values if v[0] is None]

            if numeric:
                nums = [n for n, _ in numeric]
                width = len(numeric[0][1].split('-')[-1])  # keep leading zeros

                start = prev = nums[0]

                for n in nums[1:]:
                    if n == prev + 1:
                        prev = n
                    else:
                        results.append(
                            f"{prefix}-{str(start).zfill(width)}"
                            if start == prev
                            else f"{prefix}-{str(start).zfill(width)}-{prefix}-{str(prev).zfill(width)}"
                        )
                        start = prev = n

                # last range
                results.append(
                    f"{prefix}-{str(start).zfill(width)}"
                    if start == prev
                    else f"{prefix}-{str(start).zfill(width)}-{prefix}-{str(prev).zfill(width)}"
                )

            results.extend(text_only)

        return ', '.join(results)




    @api.constrains('control_tag_ids_json')
    def _update_move_lines_from_control_tag_json(self):
        """
        When control_tag_ids_json changes, update the linked stock moves
        and create/update move lines with the serial numbers (lot_ids) from JSON.
        
        Handles:
        1. New moves created when quantity increases
        2. Tracking lots already assigned in done moves vs pending moves
        3. Selective removal of control tags (only from pending moves)
        """
        # Skip if called from context to prevent infinite loops
        if self.env.context.get('skip_control_tag_json_update'):
            return
        
        for line in self:
            if line.state != 'sale':
                continue
            
            # Ensure JSON is a dict
            if not isinstance(line.control_tag_ids_json, dict):
                continue

            # Option A (refined): interpret JSON as
            # - {task_id: {worksheet_line_id: lot_id}} (preferred)
            # - legacy {task_id: lot_id or [lot_ids...]}
            lots_by_task = defaultdict(list)
            for k, v in (line.control_tag_ids_json or {}).items():
                try:
                    task_id = int(k)
                except (ValueError, TypeError):
                    continue
                if not v:
                    continue
                if isinstance(v, dict):
                    vals = list(v.values())
                else:
                    vals = v if isinstance(v, list) else [v]
                for lot_id in vals:
                    try:
                        lot_id_int = int(lot_id) if isinstance(lot_id, (int, str)) else None
                    except (ValueError, TypeError):
                        lot_id_int = None
                    if lot_id_int:
                        lots_by_task[task_id].append(lot_id_int)

            current_lot_ids = set()
            for lots in lots_by_task.values():
                current_lot_ids |= set(lots)
            
            # Separate moves by state
            # Done moves: preserve their move lines (never touch them)
            done_moves = line.move_ids.filtered(lambda m: m.state == 'done')
            # Pending moves: can be modified (draft, waiting, confirmed, assigned, etc.)
            pending_moves = line.move_ids.filtered(
                lambda m: m.state not in ['cancel', 'done']
            ).exists().sorted('id')
           
            # if len(pending_moves) > 1:
            #     pending_moves[1:].unlink()

            #     # Reassig move so that below still can use
            #     pending_moves = pending_moves[:1]
            if not pending_moves:
                continue
            
            # Track lots already assigned in done moves (read-only, never touch)
            lots_in_done_moves = set()
            for move in done_moves:
                for ml in move.move_line_ids.filtered(
                    lambda ml: ml.product_id == line.product_id and ml.lot_id
                ):
                    lots_in_done_moves.add(ml.lot_id.id)
            
            # Track lots already assigned in pending moves
            # Structure: {lot_id: [list of move_lines]}
            lots_in_pending_moves = {}
            for move in pending_moves:
                for ml in move.move_line_ids.filtered(
                    lambda ml: ml.product_id == line.product_id and ml.lot_id
                ):
                    lot_id = ml.lot_id.id
                    if lot_id not in lots_in_pending_moves:
                        lots_in_pending_moves[lot_id] = []
                    lots_in_pending_moves[lot_id].append(ml)

            # Index pending moves by their procurement group task (if available)
            moves_by_task = defaultdict(lambda: self.env['stock.move'])
            for move in pending_moves:
                move_task = getattr(getattr(move, 'group_id', False), 'task_id', False)
                move_task_id = move_task.id if move_task else 0
                moves_by_task[move_task_id] |= move

            # Calculate which lots to add and which to remove
            # Lots to add: in JSON but not in any move (or only in done moves)
            lots_to_add = current_lot_ids - lots_in_done_moves - set(lots_in_pending_moves.keys())
            
            # Lots to remove: in pending moves but not in JSON (and not in done moves)
            lots_to_remove = set(lots_in_pending_moves.keys()) - current_lot_ids - lots_in_done_moves
            
            _logger.info(
                f"Sale Order Line {line.id}: "
                f"Lots in done moves: {lots_in_done_moves}, "
                f"Lots in pending moves: {set(lots_in_pending_moves.keys())}, "
                f"Lots to add: {lots_to_add}, "
                f"Lots to remove: {lots_to_remove}"
            )
            
            # Issue 3: Handle removal of control tags from worksheet
            # Remove lots that are no longer in JSON (only from pending moves)
            for lot_id in lots_to_remove:
                for ml in lots_in_pending_moves[lot_id]:
                    # Only remove from moves that are not done/canceled
                    if ml.move_id.state not in ['done', 'cancel']:
                        ml.with_context(skip_control_tag_json_update=True).unlink()
      
            # Issue 1 & 2: Assign lots to the correct subtask moves/pickings.
            # For each subtask_id, enforce that its lots are located on moves whose
            # procurement group carries the same task_id.
            def _create_move_line_on_move(move, lot_id):
                # Control-tag move lines must always source from the normal warehouse stock location
                # even if the picking header location is set to the service location.
                wh = self.env.ref('stock.warehouse0', raise_if_not_found=False)
                warehouse_loc = wh.lot_stock_id if wh and getattr(wh, 'lot_stock_id', False) else False
                move_line_vals = {
                    'move_id': move.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom.id,
                    'location_id': (warehouse_loc.id if warehouse_loc else move.location_id.id),
                    'location_dest_id': move.location_dest_id.id,
                    'lot_id': lot_id,
                    # Do NOT set qty_done here.
                    # Setting qty_done for control tags only causes Odoo to validate only these
                    # lines and create backorders for other products (qty_done=0).
                    # 'qty_done': 0.0,
                    'quantity': 1,
                }
                return self.env['stock.move.line'].with_context(
                    skip_control_tag_json_update=True
                ).create(move_line_vals)

            # First, remove lots that are in a "wrong" task move (pending only).
            for task_id, desired_lots in lots_by_task.items():
                desired_set = set(desired_lots)
                for lot_id in desired_set:
                    if lot_id in lots_in_done_moves:
                        continue
                    for ml in lots_in_pending_moves.get(lot_id, []):
                        ml_task = getattr(getattr(ml.move_id, 'group_id', False), 'task_id', False)
                        ml_task_id = ml_task.id if ml_task else 0
                        if ml_task_id and ml_task_id != task_id and ml.move_id.state not in ['done', 'cancel']:
                            ml.with_context(skip_control_tag_json_update=True).unlink()

            # Refresh pending lot index after removals
            pending_moves.invalidate_recordset(['move_line_ids'])
            lots_in_pending_moves = {}
            for move in pending_moves:
                for ml in move.move_line_ids.filtered(lambda ml: ml.product_id == line.product_id and ml.lot_id):
                    lot_id = ml.lot_id.id
                    lots_in_pending_moves.setdefault(lot_id, []).append(ml)

            # Now add missing lots into the correct task moves.
            for task_id, desired_lots in lots_by_task.items():
                # Prefer moves that belong to this task; fallback to any pending move.
                candidate_moves = moves_by_task.get(task_id) or pending_moves
                candidate_moves = candidate_moves.sorted('id')
                for lot_id in set(desired_lots):
                    if lot_id in lots_in_done_moves:
                        continue
                    # If already present in a correct-task move line, keep it (do not touch qty_done)
                    existing_mls = lots_in_pending_moves.get(lot_id, [])
                    already_ok = False
                    for ml in existing_mls:
                        ml_task = getattr(getattr(ml.move_id, 'group_id', False), 'task_id', False)
                        ml_task_id = ml_task.id if ml_task else 0
                        if ml_task_id == task_id or (ml_task_id == 0 and candidate_moves == pending_moves):
                            already_ok = True
                            break
                    if already_ok:
                        continue

                    # Create on a move that has capacity
                    assigned = False
                    for move in candidate_moves:
                        existing_ml_count = len(move.move_line_ids.filtered(lambda ml: ml.product_id == line.product_id))
                        if existing_ml_count < move.product_uom_qty:
                            _create_move_line_on_move(move, lot_id)
                            assigned = True
                            break
                    if not assigned and candidate_moves:
                        _create_move_line_on_move(candidate_moves[0], lot_id)
          
            # IMPORTANT: don't auto-fill qty_done here.
            # Let Odoo's standard "Set quantities" / validation logic handle done quantities
            # so the picking doesn't become a partial delivery unexpectedly.

            # Refine stock move description per DO/subtask:
            # - Keep the base description
            # - Append ONLY the Tag No(s) belonging to this move's task/group
            def _base_without_tags(text):
                if not text:
                    return ""
                return str(text).split("\nTag No:", 1)[0].rstrip()

            base_desc = _base_without_tags(line.name)

            for move in pending_moves:
                move_task = getattr(getattr(move, 'group_id', False), 'task_id', False)
                move_task_id = move_task.id if move_task else 0

                # Prefer actual assigned move lines for this move
                move_lot_names = sorted(
                    move.move_line_ids.filtered(
                        lambda ml: ml.product_id == line.product_id and ml.lot_id
                    ).mapped('lot_id.name')
                )

                # If not yet assigned, fallback to JSON bucket for this task
                if not move_lot_names and move_task_id:
                    lot_ids_for_task = lots_by_task.get(move_task_id, [])
                    move_lot_names = sorted(
                        self.env['stock.lot'].browse(list(set(lot_ids_for_task))).mapped('name')
                    )

                desc = base_desc
                if move_lot_names:
                    desc = f"{base_desc}\nTag No: {line._format_lot_ranges(move_lot_names)}"

                if move.description_picking != desc:
                    move.write({'description_picking': desc})
 
    def _update_move_descriptions_from_bus_quantities(self):
        """
        Refine stock move descriptions for bus quantities per DO/subtask:
        - Only show bus numbers relevant to the specific move's task/group
        - Similar to control tag description refinement
        """
        for line in self:
            if not isinstance(getattr(line, 'bus_quantities_by_task', None), dict) or not line.bus_quantities_by_task:
                continue
            
            # Get all moves for this line that are not cancelled
            pending_moves = line.move_ids.filtered(
                lambda m: m.state not in ('cancel', 'done') and m.picking_id
            )
            if not pending_moves:
                continue
            
            # Extract base description (without bus information)
            def _base_without_buses(text):
                if not text:
                    return ""
                # Remove bus-related sections
                lines = str(text).split('\n')
                base_lines = []
                skip_until_next_section = False
                for ln in lines:
                    if 'Servicing Date On:' in ln or 'Bus Number:' in ln or ln.strip().startswith(('1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)')):
                        skip_until_next_section = True
                        continue
                    if skip_until_next_section and not ln.strip():
                        skip_until_next_section = False
                        continue
                    if not skip_until_next_section:
                        base_lines.append(ln)
                return '\n'.join(base_lines).rstrip()
            
            base_desc = _base_without_buses(line.name)
            
            # Update each move's description based on its task
            for move in pending_moves:
                move_task = getattr(getattr(move, 'group_id', False), 'task_id', False)
                move_task_id = move_task.id if move_task else 0
                
                if not move_task_id:
                    # If no task, use the full description
                    desc = line.name
                else:
                    # Get bus quantities for THIS specific task
                    task_bucket = line.bus_quantities_by_task.get(str(move_task_id), {})
                    if not isinstance(task_bucket, dict):
                        task_bucket = {}
                    
                    if not task_bucket:
                        # No buses for this task, use base description
                        desc = base_desc
                    else:
                        # Build description with only this task's buses
                        # Parse special_id to get date information if available
                        bus_data_by_date = {}
                        if line.special_id:
                            for entry in line.special_id.split(';'):
                                if '|' in entry:
                                    date_key, buses_str = entry.split('|', 1)
                                    date_key = date_key.strip()
                                    buses = [b.strip().split('@')[0] for b in buses_str.split(',') if b.strip()]
                                    # Only include buses that are in this task's bucket
                                    task_buses = [b for b in buses if b in task_bucket]
                                    if task_buses:
                                        bus_data_by_date[date_key] = task_buses
                        
                        if bus_data_by_date:
                            # Build hierarchical format for this task only
                            parts = [base_desc] if base_desc else []
                            sorted_dates = sorted(bus_data_by_date.keys())
                            
                            for date_str in sorted_dates:
                                try:
                                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                                    formatted_date = date_obj.strftime('%d/%m/%Y')
                                except (ValueError, TypeError):
                                    formatted_date = date_str
                                
                                parts.append(f"Servicing Date On: {formatted_date}")
                                parts.append("Bus Number:")
                                
                                buses = bus_data_by_date[date_str]
                                for idx, bus in enumerate(buses, start=1):
                                    parts.append(f"{idx}){bus}")
                                
                                if date_str != sorted_dates[-1]:
                                    parts.append("")
                            
                            desc = "\n".join(parts)
                        else:
                            # Fallback: just list buses without dates
                            buses = sorted([b for b in task_bucket.keys() if task_bucket.get(b, 0) > 0])
                            if buses:
                                bus_text = ", ".join(buses)
                                desc = f"{base_desc}\n(Bus: {bus_text})" if base_desc else f"(Bus: {bus_text})"
                            else:
                                desc = base_desc
                
                if move.description_picking != desc:
                    move.write({'description_picking': desc})
          

    def update_special_description(self):
        self._update_special_description()
        
    @api.constrains('special_id')
    def _update_special_description(self):
        """
        Automatically format bus data hierarchically by servicing date.
        Format matches image structure:
        Product Description
        Servicing Date On: DD/MM/YYYY
        Bus Number:
        1) bus1
        2) bus2
        """
        for line in self:
            if not line.special_id:
                # If no bus data, keep product name only
                product_label = line.product_id.get_product_multiline_description_sale()
                if line.name != product_label:
                    line.with_context(skip_bus_update=True).write({'name': product_label})
                continue

            product_label = line.product_id.get_product_multiline_description_sale()
            
            # Parse bus data: format is "YYYY-MM-DD|bus1,bus2;YYYY-MM-DD|bus3"
            bus_data = {}
            title = False
            for entry in line.special_id.split(';'):
                if '|' in entry:
                    date_key, buses_str = entry.split('|', 1)
                    date_key = date_key.strip()
                    buses = [b.strip().split('@')[0] for b in buses_str.split(',') if b.strip()]
                    if buses:
                        bus_data[date_key] = buses
                    if not title:
                      
                        title = buses_str.strip().partition('|')[2]
                    
            
            if not bus_data:
                # Fallback: handle old format (comma-separated without dates)
                buses = [x.strip() for x in line.special_id.split(",") if x.strip()]
                if buses:
                    bus_text = ", ".join(buses)
                    new_name = f"{product_label}\n(Bus: {bus_text})"
                else:
                    new_name = product_label
            else:
                # Build hierarchical format
                parts = [product_label]
                # Sort dates chronologically
                sorted_dates = sorted(bus_data.keys())
                
                for date_str in sorted_dates:
                    # Convert YYYY-MM-DD to MM/DD/YYYY
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        # Fallback if date format is unexpected
                        formatted_date = date_str
                    
                    parts.append(f"Servicing Date On: {formatted_date}")
                    parts.append(title if title else "Bus Number:")
                    
                    # Numbered list of buses
                    buses = bus_data[date_str]
                    for idx, bus in enumerate(buses, start=1):
                        parts.append(f"{idx}){bus}")
                    
                    # Add blank line between date groups (except last)
                    if date_str != sorted_dates[-1]:
                        parts.append("")
                new_name = "\n".join(parts)

           

            # Prevent infinite write loops
            if line.name != new_name:
                # line.with_context(skip_bus_update=True).write({'name':  f"{line.product_id.get_product_multiline_description_sale()}\n{new_name}"})
                line.write({'name':  f"\n{new_name}"})


    def action_edit_service_line_details(self):
        """
        Server action to edit description, delivery date, and unit price for service products.
        Opens a wizard to edit these fields specifically for service products.
        """
        self.ensure_one()
        
     
        # Check if the sale order is locked
        if self.order_id.locked:
            raise UserError(_('Cannot edit service line details on a locked sale order.'))
        
        # Create wizard context
        wizard_context = {
            'default_sale_order_line_id': self.id,
            'default_name': self.name,
            'default_qty_delivered': self.qty_delivered,
            'default_price_unit': self.price_unit,
        }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Service Line Details'),
            'res_model': 'sale.order.line.service.edit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': wizard_context,
        }

    # deletion of sale order line if there are still moves linked to it
    def unlink(self):
        for rec in self:
            for move in rec.move_ids:
                move.unlink()
        unlinked = super().unlink()
        return unlinked
 

    # Quotation issues keep updating the delviered quantity which causing the task cannot edit the qty anymore
    @api.model_create_multi
    def create(self, vals_list):
        # If state is not 'sale', force qty_delivered to 0
        for vals in vals_list:
            if vals.get('qty_delivered') and vals.get('state') != 'sale':
                vals['qty_delivered'] = 0
        return super().create(vals_list)

    def write(self, vals):
        # If state is being set and it's not 'sale'
        if vals.get('qty_delivered') and vals.get('state') != 'sale':
            vals['qty_delivered'] = 0

        return super().write(vals)

class SaleOrderLineServiceEditWizard(models.TransientModel):
    _name = 'sale.order.line.service.edit.wizard'
    _description = 'Edit Service Line Details Wizard'

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=True,
        readonly=True
    )

    deliver_method = fields.Selection(related='sale_order_line_id.qty_delivered_method')
    name = fields.Text(
        string='Description',
        required=True,
        help='Description of the service line'
    )
    qty_delivered = fields.Float(
        string='Quantity Delivered',
        digits='Product Unit of Measure',
        help='Quantity delivered for the service'
    )
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        digits='Product Price',
        help='Unit price for the service'
    )


    @api.constrains('price_unit', 'qty_delivered')
    def _check_values(self):
        """Ensure unit price and quantity delivered are valid"""
        for record in self:
            if record.price_unit < 0:
                raise UserError(_('Unit price cannot be negative.'))
            if record.qty_delivered < 0:
                raise UserError(_('Quantity delivered cannot be negative.'))

    @api.model
    def default_get(self, fields_list):
        """Set default values from the sale order line"""
        res = super().default_get(fields_list)
        if 'sale_order_line_id' in self.env.context:
            line_id = self.env.context['sale_order_line_id']
            line = self.env['sale.order.line'].browse(line_id)
            if line.exists():
                res.update({
                    'sale_order_line_id': line.id,
                    'name': line.name,
                    'qty_delivered': line.qty_delivered,
                    'price_unit': line.price_unit,
                })
        return res

    def action_save_changes(self):
        """Save the changes to the sale order line"""
        self.ensure_one()
        
        if not self.sale_order_line_id:
            raise UserError(_('No sale order line selected.'))
        
      
        # Check if the sale order is locked
        if self.sale_order_line_id.order_id.locked:
            raise UserError(_('Cannot edit service line details on a locked sale order.'))
        
        # Update the sale order line
        self.sale_order_line_id.write({
            'name': self.name,
            'qty_delivered': self.qty_delivered,
            'price_unit': self.price_unit,
        })
        
        return {'type': 'ir.actions.act_window_close'}
