from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression

from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging
_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'product.product'

    @api.depends_context('fsm_task_id')
    def _compute_fsm_quantity(self):
        """
        Override to compute bus-specific quantity when special_id is provided.
        When filtering by bus (special_id), return quantity from bus_quantities JSON.
        IMPORTANT: Sum quantities from ALL months' lines to match _inverse_fsm_quantity logic.
        _inverse_fsm_quantity calculates diff_qty based on total across all months.
        Otherwise, return total quantity from all sale order lines.
        """
        
        task = self._get_contextual_fsm_task()
        if task:
            SaleOrderLine = self.env['sale.order.line']
            if self.env.user.has_group('project.group_project_user'):
                task = task.sudo()
                SaleOrderLine = SaleOrderLine.sudo()

            # Check if we're filtering by bus (special_id)
            context_special_id = task.current_special_id if task.current_special_id else None
            
            if context_special_id:
                # Calculate quantity from bus_quantities for the specified bus(es)
                # IMPORTANT: Sum from ALL months' lines to match _inverse_fsm_quantity
                bus_names = [b.strip() for b in str(context_special_id).split(',') if b.strip()]
                
                products_qties = SaleOrderLine._read_group(
                    [
                        ('id', 'in', task.sale_order_id.order_line.ids),
                        ('task_id', '=', task.id),
                        ('product_id', '!=', False)
                    ],
                    ['product_id'],
                    ['product_uom_qty:sum']
                )
                
                # Get bus_quantities for each product - from ALL months
                qty_dict = {}
                for product, product_uom_qty_sum in products_qties:
                    # Get ALL lines for this product (all months)
                    product_lines = SaleOrderLine.search([
                        ('id', 'in', task.sale_order_id.order_line.ids),
                        ('task_id', '=', task.id),
                        ('product_id', '=', product.id)
                    ])
                    
                    # Calculate total quantity from bus_quantities for specified buses across ALL months
                    total_bus_qty = 0
                    for line in product_lines:
                        bus_qty_dict = line.bus_quantities or {}
                        for bus_name in bus_names:
                            if bus_name in bus_qty_dict:
                                total_bus_qty += bus_qty_dict[bus_name]
                    
                    qty_dict[product.id] = total_bus_qty
                    
                for product in self:
                    product.fsm_quantity = qty_dict.get(product.id, 0)
            else:
                # No special_id - use standard computation (total quantity from all months)
                products_qties = SaleOrderLine._read_group(
                    [
                        ('id', 'in', task.sale_order_id.order_line.ids),
                        ('task_id', '=', task.id),
                        ('product_id', '!=', False)
                    ],
                    ['product_id'],
                    ['product_uom_qty:sum']
                )
                qty_dict = {product.id: product_uom_qty_sum for product, product_uom_qty_sum in products_qties}
                for product in self:
                    product.fsm_quantity = qty_dict.get(product.id, 0)
        else:
            self.fsm_quantity = False

    def set_fsm_quantity(self, quantity):
        result = super(ProjectTask, self).set_fsm_quantity(quantity)
        return result



    def _inverse_fsm_quantity(self):
        """
        Synchronize product fsm_quantity → sale.order.line qty for FSM Tasks.
        Custom logic:
        - Group by product + fsm_month (month number 1-12)
        - Create new sale order line when month changes
        - Append special_id from task.current_special_id into special_id field
        - Buses are grouped by servicing date (day) for hierarchical display
        """

        _logger.warning(f"\n\ninverse_fsm_quantity")
        task = self._get_contextual_fsm_task()
        if not task:
            return

        SaleOrderLine_sudo = self.env['sale.order.line'].sudo()
        context_special_id = task.current_special_id  # Bus name(s) - string or comma-separated
        _logger.warning(f"\n\ntask.current_special_id: {context_special_id}")

        if not context_special_id:
            result = super()._inverse_fsm_quantity()
            all_product_lines = SaleOrderLine_sudo.search([
                ('order_id', '=', task.sale_order_id.id),
                ('task_id', '=', task.id),
                ('product_uom_qty', '=', 0),
            ])
            all_product_lines.unlink()
            return result


     # Current month number (1-12)
        servicing_date = fields.Date.today()        # Use today's date for bus grouping by day
        context_month = servicing_date.month

        

        def append_special_id(line, bus_date=None, bus_qty=None, update_quantities=True, is_newly_created=False):
            """
            Append bus name with servicing date to special_id field and update bus_quantities JSON.
            Format: YYYY-MM-DD|bus1,bus2;YYYY-MM-DD|bus3,bus4
            Groups buses by servicing date (day) for hierarchical display.
            Stores quantities in bus_quantities JSON: {bus_name: qty}
            
            :param line: sale.order.line record
            :param bus_date: date to use for bus grouping (defaults to servicing_date)
            :param bus_qty: quantity to assign to the bus(es) (defaults to line quantity divided by number of buses)
            :param update_quantities: if False, only update special_id, don't modify bus_quantities
            :param is_newly_created: if True, this is a newly created line, so set quantities instead of adding
            """
            if not context_special_id:
                return

            # Use provided date or default to servicing_date
            date_to_use = bus_date or servicing_date
            
            # Convert to YYYY-MM-DD format
            if isinstance(date_to_use, datetime):
                date_str = date_to_use.strftime('%Y-%m-%d')
            elif isinstance(date_to_use, str):
                date_str = date_to_use
            elif hasattr(date_to_use, 'strftime'):
                date_str = date_to_use.strftime('%Y-%m-%d')
            else:
                date_str = str(date_to_use)
            
            # Parse existing bus data: format is "DATE|bus1,bus2;DATE|bus3"
            bus_data = {}
            if line.special_id:
                for entry in line.special_id.split(';'):
                    if '|' in entry:
                        date_key, buses_str = entry.split('|', 1)
                        date_key = date_key.strip()
                        buses = [b.strip() for b in buses_str.split(',') if b.strip()]
                        if buses:
                            bus_data[date_key] = buses
            
            # Get or create bus list for this date
            buses_for_date = bus_data.get(date_str, [])
            
            # Add new bus(es) - handle comma-separated input
            new_buses = [b.strip() for b in str(context_special_id).split(',') if b.strip()]
            for new_bus in new_buses:
                if new_bus not in buses_for_date:
                    buses_for_date.append(new_bus)
            
            # Update bus data
            if buses_for_date:
                bus_data[date_str] = buses_for_date
            
            # Rebuild special_id string: DATE|bus1,bus2;DATE|bus3
            updated_parts = []
            for date_key in sorted(bus_data.keys()):  # Sort dates chronologically
                buses_str = ','.join(bus_data[date_key])
                updated_parts.append(f"{date_key}|{buses_str}")
            
            # Write updates
            write_vals = {}
            if updated_parts:
                write_vals['special_id'] = ';'.join(updated_parts)
            
            # Update bus_quantities JSON only if update_quantities is True
            if update_quantities:
                # Read fresh from database to avoid cached values
                line.invalidate_recordset(['bus_quantities'])
                bus_quantities = dict(line.bus_quantities or {})  # Create a copy
               
                # Calculate quantity per bus
                if bus_qty is not None and bus_qty != 0:
                    # Use provided quantity - distribute equally among new buses
                    if new_buses:
                        qty_per_bus = bus_qty / len(new_buses)
                    else:
                        qty_per_bus = bus_qty
                    
               
                    # Update quantities for new buses only
                    # Check if this is a newly created line (explicit flag or no existing quantities or all are 0)
                    is_new_line = is_newly_created or not bus_quantities or all(qty == 0 for qty in bus_quantities.values())
                   
                    for bus in new_buses:
                        # If bus already exists and line is not new, add to existing quantity
                        # If bus doesn't exist or line is new, set the quantity (don't add)
                        if bus in bus_quantities and not is_new_line:
                            bus_quantities[bus] += qty_per_bus
                        else:
                            # For new lines or new buses, set the quantity directly (don't add)
                            bus_quantities[bus] = qty_per_bus
                           
                    # Calculate total quantity from bus_quantities
                    total_qty_from_buses = sum(bus_quantities.values())
                    write_vals['bus_quantities'] = bus_quantities
                    write_vals['product_uom_qty'] = total_qty_from_buses
                 
            if write_vals:
                line.write(write_vals)
                # Invalidate to ensure fresh read
                line.invalidate_recordset(['bus_quantities', 'special_id', 'product_uom_qty'])
           
        for product in self:
         
            # Get ALL lines for this product (all months) to calculate total quantity
            all_product_lines = SaleOrderLine_sudo.search([
                ('order_id', '=', task.sale_order_id.id),
                ('product_id', '=', product.id),
                ('task_id', '=', task.id),
            ])
            
            # Get or create ONE line for CURRENT month + product combination
            # Same fsm_month + same product = ONE sale order line (regardless of special_id/bus)
            current_month_line = all_product_lines.filtered(
                lambda l: l.fsm_month == str(context_month)
            )
            
            # CRITICAL: Ensure we only have ONE line per month+product
            # If multiple lines exist for same month+product, consolidate them FIRST
            if len(current_month_line) > 1:
                # Keep the first editable line, merge others into it
                editable_line = current_month_line.filtered(
                lambda l: l.qty_delivered == 0
                        or l.qty_delivered_method == 'manual'
                        or not l.order_id.locked
            )
                if editable_line:
             
                    line_to_keep = editable_line[0]
                    # Merge bus_quantities from other lines
                    merged_bus_quantities = line_to_keep.bus_quantities or {}
                    for other_line in current_month_line - line_to_keep:
                        other_bus_qty = other_line.bus_quantities or {}
                        for bus, qty in other_bus_qty.items():
                            merged_bus_quantities[bus] = merged_bus_quantities.get(bus, 0) + qty
                        # Merge special_id
                        if other_line.special_id:
                            append_special_id(line_to_keep)
                        # Delete duplicate line
                        other_line.unlink()
                    # Update line quantity to sum of bus quantities
                    total_qty = sum(merged_bus_quantities.values())
                    line_to_keep.write({
                        'product_uom_qty': total_qty,
                        'bus_quantities': merged_bus_quantities
                    })
                    current_month_line = line_to_keep
                else:
                    
                    # No editable line, keep first one and merge others
                    line_to_keep = current_month_line[0]
                    merged_bus_quantities = line_to_keep.bus_quantities or {}
                    for other_line in current_month_line[1:]:
                        other_bus_qty = other_line.bus_quantities or {}
                        for bus, qty in other_bus_qty.items():
                            merged_bus_quantities[bus] = merged_bus_quantities.get(bus, 0) + qty
                        # Merge special_id
                        if other_line.special_id:
                            append_special_id(line_to_keep)
                        # Delete duplicate line
                        other_line.unlink()
                    # Update line quantity to sum of bus quantities
                    total_qty = sum(merged_bus_quantities.values())
                    line_to_keep.write({
                        'product_uom_qty': total_qty,
                        'bus_quantities': merged_bus_quantities
                    })
                    current_month_line = line_to_keep
            elif current_month_line:
                current_month_line = current_month_line[0]
            else:
                current_month_line = False
            
            # Calculate quantities based on bus_quantities JSON
            if context_special_id:
               
                # Parse bus names from context_special_id (comma-separated)
                bus_names = [b.strip() for b in str(context_special_id).split(',') if b.strip()]
                
                # Calculate total quantity for these specific buses from bus_quantities JSON
                # IMPORTANT: Sum from ALL months' lines, not just current month
                total_qty_for_buses = 0
                for line in all_product_lines:
                    bus_qty_dict = line.bus_quantities or {}
                    for bus_name in bus_names:
                        if bus_name in bus_qty_dict:
                            total_qty_for_buses += bus_qty_dict[bus_name]
                            
               
                # Target quantity is the fsm_quantity (which represents total quantity for this bus across all months)
                target_qty = product.fsm_quantity or 0
                diff_qty = target_qty - total_qty_for_buses
            else:
 
                # Use bus_quantities sum if available, otherwise use line quantity
                current_qty = current_month_line.product_uom_qty if current_month_line else 0
                # else:
                target_qty = product.fsm_quantity or 0
                diff_qty = target_qty - current_qty
                
            # Check if line is editable
            is_editable = current_month_line and (
                current_month_line.qty_delivered == 0
                or current_month_line.qty_delivered_method == 'manual'
                or not current_month_line.order_id.locked
            )
            
            
            # ========================================================
            # 1️⃣ Update existing line for current month (ONE line per month+product)
            # ALWAYS use the same line for same month+product, regardless of special_id
            # ========================================================
            if current_month_line:
                # Only update if line is editable
                if is_editable:
                    bus_quantities = dict(current_month_line.bus_quantities or {})  # Create a copy to avoid modifying cached value
                    # Variable to store updated special_id (if it needs to be changed)
                    updated_special_id = None
                    
                    if context_special_id:
                        
                        # First, ensure buses are added to special_id structure (without changing quantities)
                        # This ensures the bus is in the special_id field for display
                        append_special_id(current_month_line, update_quantities=False)  # Only update special_id, don't touch bus_quantities
                        
                        # Now update bus quantities for specific buses based on diff_qty
                        bus_names = [b.strip() for b in str(context_special_id).split(',') if b.strip()]
                        
                        if diff_qty > 0:
                            # Increase quantity for these buses
                            qty_per_bus = diff_qty / len(bus_names) if bus_names else diff_qty
                            for bus_name in bus_names:
                                bus_quantities[bus_name] = bus_quantities.get(bus_name, 0) + qty_per_bus
                        elif diff_qty < 0:
                            # Decrease quantity for these buses and remove from special_id if quantity reaches 0
                            qty_to_remove_per_bus = abs(diff_qty) / len(bus_names) if bus_names else abs(diff_qty)
                            
                            # Parse existing special_id to remove buses with 0 quantity
                            bus_data = {}
                            if current_month_line.special_id:
                                for entry in current_month_line.special_id.split(';'):
                                    if '|' in entry:
                                        date_key, existing_buses_str = entry.split('|', 1)
                                        date_key = date_key.strip()
                                        buses = [b.strip() for b in existing_buses_str.split(',') if b.strip()]
                                        if buses:
                                            bus_data[date_key] = buses
                            
                            # Deduct quantity and remove buses with 0 quantity
                            for bus_name in bus_names:
                                if bus_name in bus_quantities:
                                    bus_quantities[bus_name] = max(0, bus_quantities[bus_name] - qty_to_remove_per_bus)
                                    
                                    # Remove bus from special_id if quantity reaches 0
                                    if bus_quantities[bus_name] == 0:
                                        # Remove from bus_data
                                        for date_key in bus_data:
                                            if bus_name in bus_data[date_key]:
                                                bus_data[date_key].remove(bus_name)
                                                # Remove date entry if no buses left
                                                if not bus_data[date_key]:
                                                    bus_data.pop(date_key, None)
                                                break
                                        # Remove from bus_quantities
                                        bus_quantities.pop(bus_name, None)
                            
                            # Rebuild special_id string without removed buses
                            updated_parts = []
                            for date_key in sorted(bus_data.keys()):
                                buses_str = ','.join(bus_data[date_key])
                                if buses_str:  # Only add if there are buses
                                    updated_parts.append(f"{date_key}|{buses_str}")
                            
                            # Store updated special_id value
                            if updated_parts:
                                updated_special_id = ';'.join(updated_parts)
                            else:
                                # No buses left, clear special_id
                                updated_special_id = False
                    else:
              
                        # No special_id - update total line quantity
                        new_qty = (current_month_line.product_uom_qty or 0) + diff_qty
                        # Distribute proportionally to existing buses, or set as single entry
                        if bus_quantities:
                            total_bus_qty = sum(bus_quantities.values())
                            if total_bus_qty > 0:
                                ratio = new_qty / total_bus_qty
                                for bus in bus_quantities:
                                    bus_quantities[bus] *= ratio
                            else:
                                # No existing buses, can't distribute
                                pass
                        else:
                            # No buses yet, will be set when append_special_id is called
                            pass
                    
                    # Calculate total quantity from bus_quantities
                    total_qty_from_buses = sum(bus_quantities.values())
                    

                                        #delete entire line if so qty = 0
                    if total_qty_from_buses == 0:
                        current_month_line.unlink()
                        continue
                    

                    # Update line with bus_quantities
                    vals = {
                        'product_uom_qty': total_qty_from_buses,
                        'bus_quantities': bus_quantities
                    }
                    # Add updated special_id if it was modified (when reducing quantity)
                    if updated_special_id is not None:
                        vals['special_id'] = updated_special_id
                    if task.under_warranty:
                        vals['price_unit'] = 0
                    
                    
                    current_month_line.with_context(fsm_no_message_post=True).write(vals)
                else:
                  
                    # Line exists but is not editable (locked/delivered)
                    # Still update special_id if possible, but don't change quantities
                    if context_special_id:
                        # Just update the bus information in special_id without changing quantities
                        append_special_id(current_month_line, update_quantities=False)
                    
                continue

            # ========================================================
            # 2️⃣ Create new sale.order.line for current month
            # ONLY create if NO line exists for this month+product combination
            # ========================================================
            # Create new line ONLY if no line exists for current month
            # We should NEVER create a duplicate - same month+product = ONE line always
            if not current_month_line and diff_qty > 0:

                # Calculate initial quantity - start with 0, let append_special_id set it correctly
                # This prevents double-counting when append_special_id is called
                initial_qty = 0
                
                vals = {
                    'order_id': task.sale_order_id.id,
                    'product_id': product.id,
                    'product_uom_qty': initial_qty,  # Start with 0, will be updated by append_special_id
                    'product_uom': product.uom_id.id,
                    'task_id': task.id,
                    'fsm_month': str(context_month),  # Store as string for consistency
                    'last_updated_date': fields.Date.today(),
                    'bus_quantities': {},  # Start empty, let append_special_id populate it
                }
                if task.under_warranty:
                    vals['price_unit'] = 0
                if product.service_type == 'manual':
                    vals['qty_delivered'] = initial_qty

                if task.sale_order_id.order_line:
                    vals['sequence'] = max(task.sale_order_id.order_line.mapped('sequence')) + 1

               
                sol_new = SaleOrderLine_sudo.create(vals)
             
                # Update special_id with bus information and set bus_quantities correctly
                # This will set the quantities (not add) since the line is new
                if context_special_id:
                    append_special_id(sol_new, bus_qty=diff_qty, update_quantities=True, is_newly_created=True)
                    # Reload to get updated values
                    sol_new.invalidate_recordset(['bus_quantities', 'special_id', 'product_uom_qty'])
                
                else:
                    # No special_id - set quantity directly
                    sol_new.write({'product_uom_qty': diff_qty})
                    if product.service_type == 'manual':
                        sol_new.write({'qty_delivered': diff_qty})
           
                   

    
    @api.depends('fsm_quantity')
    @api.depends_context('fsm_task_id', 'uid')
    def _compute_quantity_decreasable(self):
        # Compute if a product is already delivered. If a quantity is not yet delivered,
        # we can decrease the quantity

        
        task_id = self.env.context.get('fsm_task_id')
        if not task_id:
         
            self.quantity_decreasable = True
            self.quantity_decreasable_sum = 0
            return

        task = self.env['project.task'].browse(task_id)
        if not task:
            self.quantity_decreasable = False
            self.quantity_decreasable_sum = 0
            return

        moves_read_group = self.env['stock.move'].sudo()._read_group(
            [
                ('sale_line_id.order_id', '=', task.sale_order_id.id),
                ('sale_line_id.task_id', '=', task.id),
                ('product_id', 'in', self.ids),
                ('warehouse_id', '=', self.env.user.with_company(
                    task.sale_order_id.company_id.id)._get_default_warehouse_id().id),
                ('state', 'not in', ['done', 'cancel']),
            ],
            ['product_id'],
            ['product_uom_qty:sum'],
        )

        # SET THIS SO THAT EVEN IN QUOTATION ALLOW USER TO EDIT
        if not moves_read_group:
            self.quantity_decreasable = True
            self.quantity_decreasable_sum = 999

        move_per_product = {product.id: product_uom_qty for product, product_uom_qty in moves_read_group}
      
        # If no move line can be found, look into the SOL in case one line has no move and could be used to decrease the qty
        sale_lines_read_group = self.env['sale.order.line'].sudo()._read_group(
            [
                ('order_id', '=', task.sale_order_id.id),
                ('task_id', '=', task.id),
                ('product_id', 'in', self.ids),
                ('move_ids', '=', False),
            ],
            ['product_id'],
            ['product_uom_qty:sum', 'qty_delivered:sum'],
        )
        product_uom_qty_per_product = {
            product.id: product_uom_qty - qty_delivered if product.service_policy != 'delivered_manual' else product_uom_qty
            for product, product_uom_qty, qty_delivered in sale_lines_read_group
            if product_uom_qty > qty_delivered or product.service_policy == 'delivered_manual'
        }

        for product in self:
            product.quantity_decreasable_sum = move_per_product.get(product.id, product_uom_qty_per_product.get(product.id, 0))
            product.quantity_decreasable = product.quantity_decreasable_sum > 0