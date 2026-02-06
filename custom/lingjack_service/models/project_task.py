from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression
from datetime import timedelta, datetime
import logging
_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'project.task'

    name = fields.Char( default='New')
    contact_name = fields.Char(string="Contact Name")

    service_condition_id = fields.Many2one(comodel_name='service.condition', string='Service Condition', required=True)
    is_internal = fields.Boolean(related='service_condition_id.is_internal')

    partner_id = fields.Many2one(comodel_name='res.partner', string='Partner')

    # helper many2many that holds allowed locations (computed)
    service_location_ids = fields.Many2many(
        comodel_name='stock.location',
        string='Allowed Service Locations',
        compute='_compute_service_location_ids',
        store=False,   # store True if you want DB persistence
    )

    service_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Service Location',
    )
    current_special_id = fields.Char(string='Current Bus Name')

    cs_remarks = fields.Text(string='CS Remarks')



    def update_special_id(self, special_id):
        self.current_special_id = special_id
        

    @api.depends('partner_id', 'is_internal', 'service_condition_id')
    def _compute_service_location_ids(self):
        for rec in self:
            if rec.is_internal:
                # internal => locations with no customer_id
                rec.service_location_ids = [(6,0,self.env['stock.location'].search([('customer_id', '=', False)]).ids)]
            else:
                if rec.partner_id:
                 
                    partner = rec.partner_id
                    partner_parent_id = partner.parent_id.id if partner.parent_id else 0
                    domain = ['|', ('customer_id', '=', partner.id), ('customer_id', '=', partner_parent_id)]
                    # also include locations with no customer if you want:
                    # domain = ['|', ('customer_id','=',False), '|', ('customer_id','=',partner.id), ('customer_id','=',partner_parent_id)]
                   
                    rec.service_location_ids = [(6,0,self.env['stock.location'].search(domain).ids)]
                else:
                 
                    # no partner => no options (or you may choose to include customerless locations)
                    rec.service_location_ids = self.env['stock.location'].browse()

    sale_order_id = fields.Many2one(readonly=False)



    # Override planned_date_start to handle parent-child inheritance
    planned_date_start = fields.Datetime(
        compute="_compute_planned_date_start", 
        inverse='_inverse_planned_date_start', 
        search="_search_planned_date_start",
        recursive=True,
    )

    def add_control_tag_to_product(self, lot_ids=None, record_id=None, product_id=None, task_id=None):
        """
        Add the FSM control tag product on a sale order line and
        attach one or many lots (similar to fsm_lot_id behaviour).
        Refined:
        - `record_id` is the worksheet line id (or record) used as the replacement key.
        - `task_id` (or `record_id.x_studio_task`) determines which subtask bucket the lot belongs to.
        - JSON structure becomes:
          { "<task_id>": { "<worksheet_line_id>": <lot_id> }, ... }
        Keep a SINGLE control-tag sale order line for the whole sale order.
        """

        self.ensure_one()
        lot_ids = [lid for lid in (lot_ids or []) if lid]

        # Resolve worksheet line id (record_id) to an int if possible.
        worksheet_line_id = None
        if record_id is not None:
            worksheet_line_id = getattr(record_id, "id", None) or record_id
            try:
                worksheet_line_id = int(worksheet_line_id)
            except (TypeError, ValueError):
                worksheet_line_id = None

        # Resolve owner task/subtask id.
        owner_task_id = None
        if task_id is not None:
            owner_task_id = getattr(task_id, "id", None) or task_id
            try:
                owner_task_id = int(owner_task_id)
            except (TypeError, ValueError):
                owner_task_id = None
        if not owner_task_id and record_id is not None and hasattr(record_id, "x_studio_task") and record_id.x_studio_task:
            owner_task_id = record_id.x_studio_task.id
        if not owner_task_id:
            owner_task_id = self.id
        if not self.env["project.task"].browse(owner_task_id).exists():
            owner_task_id = self.id
    
        control_tag_product = product_id if product_id else self.env.company.fsm_control_tag_product_id
        if not control_tag_product:
            raise UserError(
                _("Please configure an FSM Control Tag Product in the Field Service settings.")
            )

   
        sale_order = self._fsm_ensure_sale_order()
        # Always link the control-tag SOL to the root task (single line for all subtasks)
        root_task = self
        while root_task.parent_id:
            root_task = root_task.parent_id
      
        SaleOrderLine = self.env['sale.order.line'].sudo()
        line_domain = [
            ('order_id', '=', sale_order.id),
            ('product_id', '=', control_tag_product.id),
        ]
        line = SaleOrderLine.search(line_domain, limit=1)
    
        # Get current JSON mapping (default to empty dict)
        control_tag_json = line.control_tag_ids_json if line else {}
        if not isinstance(control_tag_json, dict):
            control_tag_json = {}

        if not lot_ids:
            # Nothing to remove if the subtask doesn't have a control-tag line yet.
            if not line:
                return

            # Remove mapping for this worksheet line under the correct task bucket.
            task_bucket = control_tag_json.get(str(owner_task_id))
            if isinstance(task_bucket, dict) and worksheet_line_id:
                task_bucket.pop(str(worksheet_line_id), None)
                if not task_bucket:
                    control_tag_json.pop(str(owner_task_id), None)

            # Flatten remaining lot ids (support both new nested dict and legacy shapes)
            remaining_lot_ids = []
            for v in (control_tag_json or {}).values():
                if not v:
                    continue
                if isinstance(v, dict):
                    remaining_lot_ids.extend([x for x in v.values() if x])
                elif isinstance(v, list):
                    remaining_lot_ids.extend([x for x in v if x])
                else:
                    remaining_lot_ids.append(v)
            line.write({
                'control_tag_ids_json': control_tag_json,
                'control_tag_ids': [(6, 0, remaining_lot_ids)],
            })
            line.product_uom_qty = len(remaining_lot_ids)

            if len(remaining_lot_ids) == 0:
                line.unlink()
            return

        
        # Get current many2many lot IDs
        current_lot_ids = set(line.control_tag_ids.ids) if line else set()
        
        # Handle worksheet-line replacement logic (within owner_task_id bucket)
        if worksheet_line_id:
            task_bucket = control_tag_json.get(str(owner_task_id))
            if not isinstance(task_bucket, dict):
                task_bucket = {}

            old_lot_id = task_bucket.get(str(worksheet_line_id))
            if old_lot_id and old_lot_id in current_lot_ids:
                current_lot_ids.discard(old_lot_id)

            # Store ONE lot per worksheet line (replacement behavior)
            task_bucket[str(worksheet_line_id)] = lot_ids[0] if lot_ids else False
            control_tag_json[str(owner_task_id)] = task_bucket

            if lot_ids:
                current_lot_ids.add(lot_ids[0])
            
            # Prepare final lot IDs list
            final_lot_ids = list(current_lot_ids)
            
            if not line:
                # Create new line with record_id mapping
                create_vals = {
                    'order_id': sale_order.id,
                    'task_id': root_task.id,
                    'product_id': control_tag_product.id,
                    'product_uom_qty': len(final_lot_ids),
                    'control_tag_ids_json': control_tag_json,
                    'control_tag_ids': [(6, 0, final_lot_ids)],
                }
                line = SaleOrderLine.create(create_vals)
            else:
                # Update existing line
                line.write({
                    'control_tag_ids': [(6, 0, final_lot_ids)],
                    'control_tag_ids_json': control_tag_json
                    
                })
        else:
            # No record_id provided - just add lots normally (avoid duplicates)
            to_add = [lid for lid in lot_ids if lid not in current_lot_ids]
            
            if not line:
                # Create new line without record_id
                final_lot_ids = lot_ids
                create_vals = {
                    'order_id': sale_order.id,
                    'task_id': root_task.id,
                    'product_id': control_tag_product.id,
                    'product_uom_qty': len(final_lot_ids),
                    'state': 'draft',
                    'control_tag_ids_json': control_tag_json,  # Keep existing JSON (empty dict)
                    'control_tag_ids': [(6, 0, final_lot_ids)],
                }
                line = SaleOrderLine.create(create_vals)
            else:
                # Update existing line
                if to_add:
                    final_lot_ids = list(current_lot_ids | set(to_add))
                    line.write({
                        'control_tag_ids': [(4, lid) for lid in to_add],
                        'control_tag_ids_json': control_tag_json  # Keep existing JSON
                    })
                else:
                    final_lot_ids = list(current_lot_ids)

        line.product_uom_qty = len(final_lot_ids)
        return line

    def _append_special_id_to_line(self, line, special_id_input, bus_qty=None, is_newly_created=False):
        """
        Append bus name with servicing date to special_id field and update bus_quantities JSON.
        Format: YYYY-MM-DD|bus1,bus2;YYYY-MM-DD|bus3,bus4
        Groups buses by servicing date (day) for hierarchical display.
        Stores quantities in bus_quantities JSON: {bus_name: qty}
        
        :param line: sale.order.line record
        :param special_id_input: Format "YYYY-MM-DD|bus" or "YYYY-MM-DD|bus1,bus2"
        :param bus_qty: quantity to assign to the bus(es) (defaults to line quantity divided by number of buses)
        :param is_newly_created: if True, this is a newly created line, so set quantities instead of adding
        """
        if not special_id_input:
            return

        # Accept both formats:
        # - "YYYY-MM-DD|bus" or "YYYY-MM-DD|bus1,bus2"
        # - "bus" or "bus1,bus2" (worksheet may pass buses without date)
        raw = str(special_id_input)
        if '|' in raw:
            date_str, buses_str = raw.split('|', 1)
            date_str = date_str.strip()
        else:
            # Default date bucket (same approach as your sale.order logic)
            date_val = fields.Date.today() + timedelta(days=3)
            date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
            buses_str = raw

        new_buses = [b.strip() for b in str(buses_str).split(',') if b.strip()]
        
        if not new_buses:
            return
        
        # Parse existing bus data: format is "DATE|bus1,bus2;DATE|bus3"
        bus_data = {}
        if line.special_id:
            for entry in line.special_id.split(';'):
                if '|' in entry:
                    date_key, existing_buses_str = entry.split('|', 1)
                    date_key = date_key.strip()
                    buses = [b.strip() for b in existing_buses_str.split(',') if b.strip()]
                    if buses:
                        bus_data[date_key] = buses
        
        # Get or create bus list for this date
        buses_for_date = bus_data.get(date_str, [])
        
        # Add new bus(es) - avoid duplicates
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
        
        # Write updates (special_id string)
        write_vals = {}
        if updated_parts:
            write_vals['special_id'] = ';'.join(updated_parts)
        
        # Update bus_quantities JSON (aggregated) + bus_quantities_by_task (per subtask)
        # Read fresh from database to avoid cached values
        line.invalidate_recordset(['bus_quantities', 'bus_quantities_by_task'])
        # IMPORTANT: Always preserve existing buckets from other subtasks.
        # Read stored value and ensure we have a proper dict copy
        raw_by_task = getattr(line, 'bus_quantities_by_task', None)
        if raw_by_task and isinstance(raw_by_task, dict):
            # Deep copy: preserve all existing task buckets
            bus_quantities_by_task = {k: dict(v) if isinstance(v, dict) else v for k, v in raw_by_task.items()}
        else:
            bus_quantities_by_task = {}
        
        # Get or create THIS subtask's bucket (preserve existing buses in this bucket)
        task_bucket = dict(bus_quantities_by_task.get(str(self.id), {}) or {})
        
        # Calculate quantity per bus
        if bus_qty is not None and float(bus_qty) != 0.0:
            # Use provided quantity - distribute equally among new buses
            if new_buses:
                qty_per_bus = bus_qty / len(new_buses)
            else:
                qty_per_bus = bus_qty
            
            for bus in new_buses:
                # Per-task bucket update (append, don't replace)
                task_bucket[bus] = task_bucket.get(bus, 0.0) + qty_per_bus

            # Update only THIS subtask's bucket, preserve all others
            bus_quantities_by_task[str(self.id)] = task_bucket

            # Recompute aggregated bus quantities from all task buckets
            aggregated = {}
            for bkt in bus_quantities_by_task.values():
                if not isinstance(bkt, dict):
                    continue
                for bus, qty in bkt.items():
                    aggregated[bus] = aggregated.get(bus, 0.0) + (qty or 0.0)

            total_qty_from_buses = sum(aggregated.values())
            write_vals['bus_quantities_by_task'] = bus_quantities_by_task
            write_vals['bus_quantities'] = aggregated
            write_vals['product_uom_qty'] = total_qty_from_buses
        
        if write_vals:
            line.write(write_vals)
            # Invalidate to ensure fresh read
            line.invalidate_recordset(['bus_quantities_by_task', 'bus_quantities', 'special_id', 'product_uom_qty'])

    def _deduct_special_id_from_line(self, line, special_id_input, bus_qty):
        """
        Deduct quantity from bus(es) specified in special_id and update bus_quantities JSON.
        Removes buses from special_id if their quantity reaches 0.
        
        :param line: sale.order.line record
        :param special_id_input: Format "YYYY-MM-DD|bus" or "YYYY-MM-DD|bus1,bus2"
        :param bus_qty: quantity to deduct from the bus(es)
        :return: True if line should be unlinked (all quantities are 0), False otherwise
        """
        if not special_id_input:
            return False

        raw = str(special_id_input)
        if '|' in raw:
            _date_str, buses_str = raw.split('|', 1)
        else:
            buses_str = raw
        buses_to_deduct = [b.strip() for b in str(buses_str).split(',') if b.strip()]
        
        if not buses_to_deduct:
            return False
        
        # Read fresh from database to avoid cached values
        line.invalidate_recordset(['bus_quantities_by_task', 'bus_quantities', 'special_id'])
        # IMPORTANT: Preserve all existing task buckets (deep copy)
        raw_by_task = getattr(line, 'bus_quantities_by_task', None)
        if raw_by_task and isinstance(raw_by_task, dict):
            bus_quantities_by_task = {k: dict(v) if isinstance(v, dict) else v for k, v in raw_by_task.items()}
        else:
            bus_quantities_by_task = {}
        task_bucket = dict(bus_quantities_by_task.get(str(self.id), {}) or {})
        
        # Parse existing bus data: format is "DATE|bus1,bus2;DATE|bus3"
        bus_data = {}
        if line.special_id:
            for entry in line.special_id.split(';'):
                if '|' in entry:
                    date_key, existing_buses_str = entry.split('|', 1)
                    date_key = date_key.strip()
                    buses = [b.strip() for b in existing_buses_str.split(',') if b.strip()]
                    if buses:
                        bus_data[date_key] = buses
        
        # Calculate quantity per bus to deduct (distribute equally)
        qty_per_bus = bus_qty / len(buses_to_deduct) if buses_to_deduct else bus_qty
        
        # Deduct quantity from each bus for THIS subtask bucket
        for bus in buses_to_deduct:
            if bus in task_bucket:
                task_bucket[bus] = max(0.0, (task_bucket.get(bus, 0.0) - qty_per_bus))
                if task_bucket[bus] == 0:
                    task_bucket.pop(bus, None)

        if task_bucket:
            bus_quantities_by_task[str(self.id)] = task_bucket
        else:
            bus_quantities_by_task.pop(str(self.id), None)

        # Recompute aggregated bus quantities from all task buckets
        bus_quantities = {}
        for bkt in bus_quantities_by_task.values():
            if not isinstance(bkt, dict):
                continue
            for bus, qty in bkt.items():
                bus_quantities[bus] = bus_quantities.get(bus, 0.0) + (qty or 0.0)

        # Remove buses from special_id only if their aggregated qty is now 0
        for bus in buses_to_deduct:
            if bus not in bus_quantities or bus_quantities.get(bus, 0.0) == 0:
                for date_key in list(bus_data.keys()):
                    if bus in bus_data.get(date_key, []):
                        bus_data[date_key].remove(bus)
                        if not bus_data[date_key]:
                            bus_data.pop(date_key, None)
        
        # Rebuild special_id string: DATE|bus1,bus2;DATE|bus3
        updated_parts = []
        for date_key in sorted(bus_data.keys()):  # Sort dates chronologically
            buses_str = ','.join(bus_data[date_key])
            if buses_str:  # Only add if there are buses
                updated_parts.append(f"{date_key}|{buses_str}")
        
        # Calculate total quantity from bus_quantities
        total_qty_from_buses = sum(bus_quantities.values())
        
        # Prepare write values
        write_vals = {}
        if updated_parts:
            write_vals['special_id'] = ';'.join(updated_parts)
        else:
            # No buses left, clear special_id
            write_vals['special_id'] = False
        
        write_vals['bus_quantities_by_task'] = bus_quantities_by_task
        write_vals['bus_quantities'] = bus_quantities if bus_quantities else {}
        write_vals['product_uom_qty'] = total_qty_from_buses
        
        if write_vals:
            line.write(write_vals)
            # Invalidate to ensure fresh read
            line.invalidate_recordset(['bus_quantities_by_task', 'bus_quantities', 'special_id', 'product_uom_qty'])
        
        # Return True if all quantities are 0 (line should be unlinked)
        return total_qty_from_buses == 0

    def add_normal_product(self, product_id=None, type_name=None, type="add", quantity=1.0, special_id=None):
        """
        Add or deduct a normal product on a sale order line.
        
        :param product_id: Product to add/deduct (required)
        :param type_name: Type identifier for grouping similar product lines (required)
        :param type: "add" to add quantity, "deduct" to deduct quantity (default: "add")
        :param quantity: Quantity to add/deduct (default: 1.0)
        :param special_id: Format "YYYY-MM-DD|bus" or "YYYY-MM-DD|bus1,bus2" to associate with bus(es)
        :return: The sale order line record
        """
        self.ensure_one()
        
        if not product_id:
            raise UserError(_("Product ID is required."))

        
        if quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))
        
        # Ensure sale order exists and get it
        sale_order = self._fsm_ensure_sale_order()
        if not sale_order:
            raise UserError(_("No sale order is linked to this task."))
        
        # Use sudo() to ensure we can access the sale order and its lines
        SaleOrderLine = self.env['sale.order.line'].sudo()
        # Search for grouped line by (product_id, type_name) regardless of task_id
        # so multiple subtasks can share the same SO line.
        line_domain = [
            ('order_id', '=', sale_order.id),
            ('product_id', '=', product_id),
        ]
        
        if type_name:
            line_domain.append(('type_name', '=', type_name))
        else:
            # If no type_name, also check for lines without type_name
            line_domain.append(('type_name', '=', False))

        line = SaleOrderLine.search(line_domain, limit=1)
       
        if type == "add":
            is_newly_created = False
            if not line:
                line_domain = [
                    ('order_id', '=', sale_order.id),
                    ('product_id', '=', product_id),
                    ('type_name','=', False),
                ]

                line_no_type = SaleOrderLine.search(line_domain, limit=1)
      
                # Create new line
                product = self.env['product.product'].browse(product_id)
                if not product.exists():
                    raise UserError(_("Product not found."))
                
                # Initialize with empty bus_quantities if special_id is provided
                create_vals = {
                    'order_id': sale_order.id,
                    'task_id': self.id,
                    'product_id': product_id,
                    # Always keep type_name so same (product_id, type_name) merges into one line,
                    # even when special_id/bus logic is used.
                    'type_name': type_name,
                    'product_uom_qty': 0 if special_id else quantity,  # Will be set by _append_special_id_to_line if special_id
                    'state': 'draft',
                    'bus_quantities': {} if special_id else False,
                    'bus_quantities_by_task': {} if special_id else {},  # Always initialize as dict
                    'product_uom_qty_by_task': {} if special_id else {str(self.id): quantity},  # type_name-only: split by task
                }
                line = SaleOrderLine.create(create_vals)
                is_newly_created = True
             
                # We need to do this is because service team might create sale order line frist so it will not link to task hence cauysing issues
                if line_no_type:
                    line.write({
                        'price_unit': line_no_type.price_unit,
                    })
                    line_no_type.unlink()

            else:
                # Add quantity to existing line
                # If special_id is provided, quantity will be handled by _append_special_id_to_line
                if not special_id:
                    if type_name:
                        # type_name-only: track per task so procurements split by subtask
                        line.invalidate_recordset(['product_uom_qty_by_task'])
                        raw_by_task = getattr(line, 'product_uom_qty_by_task', None) or {}
                        by_task = dict(raw_by_task) if isinstance(raw_by_task, dict) else {}
                        # Migrate existing product_uom_qty into by_task if line had no by_task yet
                        if not by_task and line.product_uom_qty:
                            existing_task = (line.task_id and line.task_id.id) or self.id
                            by_task[str(existing_task)] = float(line.product_uom_qty)
                        by_task[str(self.id)] = by_task.get(str(self.id), 0.0) + quantity
                        line.write({
                            'product_uom_qty_by_task': by_task,
                            'product_uom_qty': sum((x or 0.0) for x in by_task.values() if isinstance(x, (int, float))),
                        })
                    else:
                        new_quantity = line.product_uom_qty + quantity
                        line.write({
                            'product_uom_qty': new_quantity,
                        })

            # Handle special_id with enhanced logic
            if special_id:
                # Use the provided quantity for bus_quantities
                self._append_special_id_to_line(line, special_id, bus_qty=quantity, is_newly_created=is_newly_created)
            return line
        
        elif type == "deduct":
            if not line:
                raise UserError(
                    _("No sale order line found with product '%s' and type '%s' to deduct from.")
                    % (self.env['product.product'].browse(product_id).display_name, type_name)
                )
            
            # Handle special_id with enhanced logic
            if special_id:
                # Use the new deduct method for special_id
                should_unlink = self._deduct_special_id_from_line(line, special_id, bus_qty=quantity)
                if should_unlink:
                    # If all quantities become zero, unlink the line
                    line.unlink()
                    return self.env['sale.order.line']  # Return empty recordset
            else:
                # Standard deduct logic (no special_id)
                if type_name and getattr(line, 'product_uom_qty_by_task', None):
                    raw_by_task = line.product_uom_qty_by_task or {}
                    by_task = dict(raw_by_task) if isinstance(raw_by_task, dict) else {}
                    current = by_task.get(str(self.id), 0.0) or 0.0
                    by_task[str(self.id)] = max(0.0, current - quantity)
                    if by_task[str(self.id)] == 0:
                        by_task.pop(str(self.id), None)
                    total = sum((x or 0.0) for x in by_task.values() if isinstance(x, (int, float)))
                    line.write({
                        'product_uom_qty_by_task': by_task if by_task else {},
                        'product_uom_qty': total,
                    })
                    if total <= 0:
                        line.unlink()
                        return self.env['sale.order.line']
                    return line
                # Deduct quantity (ensure it doesn't go below 0)
                new_quantity = max(0.0, line.product_uom_qty - quantity)
                
                if new_quantity == 0:
                    # If quantity becomes zero, unlink the line
                    line.unlink()
                    return self.env['sale.order.line']  # Return empty recordset
                else:
                    line.write({
                        'product_uom_qty': new_quantity,
                    })
        else:
            raise UserError(_("Type must be either 'add' or 'deduct'."))
        
        return line

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to:
        1. Prevent creating a subtask of a subtask (only one level allowed).
        2. Ensure proper sale order synchronization after creation.
        """
        # Collect all parent task IDs from incoming values
        parent_ids = {
            vals.get('parent_id')
            for vals in vals_list
            if vals.get('parent_id')
        }

        if parent_ids:
            parent_tasks = self.env['project.task'].browse(parent_ids)
            invalid_parents = parent_tasks.filtered(lambda t: t.parent_id)
            if invalid_parents:
                raise UserError(
                    _("You cannot create a subtask for a subtask. Only one level of subtask is allowed.")
                )

        # Create tasks
        tasks = super().create(vals_list)

        # Post-create logic
        for task, vals in zip(tasks, vals_list):
            if vals.get('sale_order_id'):
                task.with_context(skip_sale_order_sync=False).write({
                    'sale_order_id': task.sale_order_id.id,
                })

        return tasks
        
    def action_fsm_validate(self, stop_running_timers=False):
        # Keep Odoo standard behavior (timers + done), but tell downstream code to skip SO confirm
        return super(ProjectTask, self.with_context(fsm_skip_so_confirm=True)).action_fsm_validate(
            stop_running_timers=stop_running_timers
        )

    def _prepare_materials_delivery(self):
        if self.env.context.get("fsm_skip_so_confirm"):
            return
        return super()._prepare_materials_delivery()

    @api.constrains('create_uid')
    def name_create(self):
        '''
        Assign the id as the name of the task. when create task from name.
        '''
        for task in self:
            if task.name == _('New'):
                task.name = f"{task.id:06d}"

    def write(self, vals):
        """Override write to handle parent-child date inheritance"""
        result = super(ProjectTask, self).write(vals)

        if self.env.context.get("skip_sale_order_sync"):
            return result

        # If parent_id is being set, inherit dates from parent
        if 'parent_id' in vals and vals['parent_id']:
            parent_task = self.env['project.task'].browse(vals['parent_id'])
            if parent_task.exists():
                # Only update if the fields are not already being set in vals
                update_vals = {}
                if 'planned_date_begin' not in vals and parent_task.planned_date_begin:
                    update_vals['planned_date_begin'] = parent_task.planned_date_begin
                if 'date_deadline' not in vals and parent_task.date_deadline:
                    update_vals['date_deadline'] = parent_task.date_deadline
                if update_vals:
                    super(ProjectTask, self).write(update_vals)

        #########################################################################################
        # This function is used to sync the sale order id to the parent and child tasks 
        #########################################################################################


        # Only run when sale_order_id is updated
        if "sale_order_id" in vals:
            for task in self:
                so_id = task.sale_order_id.id  # after write()

                # Build set: self + parents chain + all descendants
                tasks_to_update = task

                # parents chain
                cur = task.parent_id
                while cur:
                    tasks_to_update |= cur
                    cur = cur.parent_id

                # descendants (children, grandchildren, ...)
                tasks_to_update |= self.search([("id", "child_of", task.id)])

                tasks_to_update.with_context(skip_sale_order_sync=True).write({
                    "sale_order_id": so_id
                })

        #########################################################################################
        # Sync CS remarks from parent task to DO remarks when cs_remarks is updated
        #########################################################################################
        if "cs_remarks" in vals:
            # Only sync for parent tasks (tasks without a parent_id)
            parent_tasks = self.filtered(lambda t: not t.parent_id)
            if parent_tasks:
                parent_tasks._sync_cs_remarks_to_do_remarks()

        return result

    @api.onchange('tag_ids')
    def _updated_description_with_tag(self):
        for rec in self:
            if not rec.parent_id:
                rec.description = "\n".join(rec.tag_ids.filtered(lambda rev: rev.description).mapped('description'))

    @api.constrains('parent_id')
    def _constrains_parent_id_tags(self):
        """Inherit properties from parent task when creating subtask"""
        if self.parent_id:
            self.contact_name = self.parent_id.contact_name
            self.description = self.parent_id.description

    def get_default_subtask_time(self):
        # get current UTC time and adjust to UTC+8
        now_utc = fields.Datetime.now() + timedelta(hours=8)
        # set to 9:00 and 17:00 local (then back to UTC)
        start_utc = now_utc.replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(hours=8)
        end_utc = now_utc.replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(hours=8)

        self.planned_date_begin = start_utc
        self.date_deadline = end_utc
            
    @api.onchange('parent_id')
    def _onchange_parent_id_tags(self):
        """Inherit properties from parent task when creating subtask"""
        if self.parent_id:
            self.tag_ids = self.parent_id.tag_ids
            self.partner_phone = self.parent_id.partner_phone

            self.user_ids = []
            # Use Current time
            self.get_default_subtask_time()

            self.service_condition_id = self.parent_id.service_condition_id.id
            self.service_location_id = self.parent_id.service_location_id.id
            self.sale_order_id = self.parent_id.sale_order_id.id

    @api.constrains('parent_id')
    def _constrains_parent_id_tags(self):
        """Inherit properties from parent task when creating subtask"""
        self._onchange_parent_id_tags()

    @api.onchange('tag_ids', 'description', 'contact_name', 'planned_date_begin', 'date_deadline')
    def sync_to_subtasks(self):
        """Sync parent task changes to all subtasks"""
        for rec in self:
            # Only apply if it's a parent task
            if rec.child_ids:
                for child in rec.child_ids:
                    child.tag_ids = rec.tag_ids.ids
                    child.description = rec.description
                    child.contact_name = rec.contact_name
                    child.partner_phone = rec.partner_phone
                    # Sync date fields from parent to subtasks
                    child.planned_date_begin = rec.planned_date_begin
                    child.date_deadline = rec.date_deadline
                    child.date_end = rec.date_end

                    child.service_condition_id = rec.service_condition_id.id
                    child.service_location_id = rec.service_location_id.id

    @api.depends('planned_date_begin', 'date_deadline', 'parent_id', 'parent_id.planned_date_start')
    def _compute_planned_date_start(self):
        for task in self:
            if task.parent_id:
                # For subtasks, inherit the planned_date_start from parent
                task.planned_date_start = task.parent_id.planned_date_start
            else:
                # For parent tasks, use the standard logic from project_enterprise
                task.planned_date_start = task.planned_date_begin or task.date_deadline

    def _inverse_planned_date_start(self):
        """ Inverse method only used for calendar view to update the date start if the date begin was defined """
        for task in self:
            if not task.parent_id:
                # Only allow date changes for parent tasks
                if task.planned_date_begin:
                    task.planned_date_begin = task.planned_date_start
                else:  # to keep the right hour in the date_deadline
                    task.date_deadline = task.planned_date_start
            # For subtasks, we don't allow direct modification of planned_date_start
            # as it should always follow the parent


    def action_fsm_view_material(self):
        """
        Refined action to show FSM materials with quantity on hand in configured locations.
        Only shows products that have stock in the company's configured FSM material locations.
        """
       
        action = super(ProjectTask, self).action_fsm_view_material()
        
        # Get the company's configured FSM material locations
        company = self.env.company
        # fsm_locations = company.fsm_material_location_ids
        if self.service_condition_id.is_internal:
            fsm_locations = self.env['stock.location'].sudo().search([('customer_id', '=', False)]) if not self.service_location_id else self.service_location_id
        else:
            fsm_locations = self.service_location_id

        if fsm_locations:
            # Get products with quantity on hand in the configured locations
            stock_quant_domain = [
                ('location_id', 'in', fsm_locations.ids),
                ('quantity', '>', 0)
            ]
        
            # Get product IDs that have stock in the configured locations
            stock_quants = self.env['stock.quant'].search(stock_quant_domain)
            product_ids_with_stock = stock_quants.mapped('product_id.id')
            
            # Add domain filter to only show products with stock in configured locations
            if product_ids_with_stock:
                # Combine with existing domain using AND
                existing_domain = action.get('domain', [])
                stock_domain = [('sale_ok','=',True),'|', '&', ('id', 'in', product_ids_with_stock),('type', '=', 'consu'),('service_always_show', '=', True)]
                action['domain'] = expression.AND([existing_domain, stock_domain])
            else:
                # If no products have stock, show empty result
                action['domain'] = [('sale_ok','=',True),'|',('id', '=', False),('service_always_show', '=', True)]
        else:
            # If no products have stock, show empty result
            action['domain'] = [('sale_ok','=',True),'|',('id', '=', False),('service_always_show', '=', True)]
           
        existing_context = action.get('context', {})
        existing_context['special_id'] = self.env.context.get('special_id')
        return action


    def _prepare_sale_order_values(self, team):
        vals = super(ProjectTask, self)._prepare_sale_order_values(team)
        vals.update({
            'quotation_type': 'order_processing',
            'sale_type_id': self.service_condition_id.sale_type.id,
            'user_id': 0,
        })
        return vals

    def _fsm_ensure_sale_order(self):
        """
        Ensure that a task and all its subtasks share a single sale order.
        The sale order is always created/ensured on the root (top-level) task,
        then propagated to the whole hierarchy.
        """
        self.ensure_one()

        # Always work with the root task so we never create multiple SOs
        root_task = self
        while root_task.parent_id:
            root_task = root_task.parent_id
        root_task = root_task.sudo()

        # Let the standard FSM logic create/ensure the sale order on the root task
        sale_order = super(ProjectTask, root_task)._fsm_ensure_sale_order()

        if not sale_order:
            return sale_order

        # Assign the partner's salesperson as the sale order salesperson
        sale_order.user_id = sale_order.partner_id.user_id or 0

        # Track approval status if all reviews are approved
        if all(sale_order.review_ids.filtered(lambda x: x.status == 'approved')):
            sale_order.approve = True
            sale_order.approved_by = self.env.user
            sale_order.approved_on = fields.Datetime.now()

        # Ensure the sale order partner is not the parent address, based on root task partner
        root_task.ensure_sale_order_partner_not_is_parent_address(sale_order)

        # Propagate the sale order to the full hierarchy (root + all descendants),
        # using context flag to avoid re-triggering sync logic in write()
        tasks_to_update = root_task | self.search([("id", "child_of", root_task.id)])
        tasks_to_update.with_context(skip_sale_order_sync=True).write({
            "sale_order_id": sale_order.id,
        })

        return sale_order

    def ensure_sale_order_partner_not_is_parent_address(self, order_id):
        """Ensure the sale order partner is not the parent address"""

        partner_id = self.partner_id.parent_id if self.partner_id.parent_id else self.partner_id
        if partner_id != order_id.partner_id:
            order_id.write({
                'partner_id': partner_id.id,
            })
        return True

    def _sync_cs_remarks_to_do_remarks(self):
        """
        Sync CS remarks from parent task to DO remarks in all delivery orders
        linked to the sale order. If do_remarks already has content, append cs_remarks on next line.
        """
        for task in self:
            # Only process parent tasks (tasks without a parent)
            if task.parent_id:
                continue
            
            # Only process if task has cs_remarks and a sale order
            if not task.cs_remarks or not task.sale_order_id:
                continue
            
            # Get all delivery orders linked to the sale order
            delivery_orders = self.env['stock.picking'].search([
                ('sale_id', '=', task.sale_order_id.id),
                ('state', 'not in', ['cancel', 'done']),
                ('picking_type_id.code', '=', 'outgoing')  # Only outgoing delivery orders
            ])
            
            if not delivery_orders:
                continue
            
            # Update do_remarks for each delivery order
            for picking in delivery_orders:
                if picking.do_remarks and picking.do_remarks.strip():
                    # Append on next line if do_remarks already has content
                    picking.do_remarks = f"{picking.do_remarks}\n{task.cs_remarks}"
                else:
                    # Set directly if do_remarks is empty
                    picking.do_remarks = task.cs_remarks

    # def _fsm_create_sale_order(self):
    #     """Super this function to remove assign current user as salepperson in sale order"""
    #     super()._fsm_create_sale_order()
        # Get sale order with sudo() to ensure access rights

class ProjectTags(models.Model):
    _inherit = 'project.tags'

    description = fields.Html('Description')