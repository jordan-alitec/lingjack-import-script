from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.http import request
from collections import defaultdict
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_service_type = fields.Boolean(string='Is Service Type', default=False, compute="_compute_is_service")

    def _compute_is_service(self):
        for so in self:
            so.is_service_type = so.sale_type_id.is_service
            
    @api.depends('order_line')
    def _compute_is_service_products(self):
        for so in self:
            so.is_all_service = all(line.product_id.type == 'service' for line in so.order_line.filtered(lambda x: not x.display_type))


    def action_lock(self):
        '''
        Override to prevent locking a sale order with service products.
        Once locked, field service not able to add the component into the order.
        Technician will stuck in the field service view.
        '''
        for so in self:
            if so.sale_type_id.is_service:
                return
            so.locked = True

    def action_confirm(self):
        # Early returns for your FSM keys
        if self.env.context.get('fsm_task_id'):
            return True

        if self.env.context.get("fsm_skip_so_confirm"):
            return True



        #### !iimportant dont delete this code ####
        #### Odoo will pass active_id and active_ids of current record id to the the context when user gone through other model through smart button
        #### And base tier valdiation read the active_ids and treat as current model record id

        ### Scenario
        # User click the action_view_so in project task form view
        # Odoo will pass active_id and active_ids of project task record id to the the context
        # and when we do action confirm
        # base tier valdiation will read the active_ids and treat as sale order record id but it was project task record id

        ctx = dict(self.env.context)
        ctx.pop('active_id', None)  # remove active_id safely
        ctx.pop('active_ids', None)

        # Call super with modified context
        return super(SaleOrder, self.with_context(ctx)).action_confirm()



    def _get_product_catalog_record_lines(self, product_ids, **kwarg):
        """
            Accessing the catalog from the smart button of a "field service" should compute
            the content of the catalog related to that field service rather than the content
            of the catalog related to the sale order containing that "field service".
        """
        task_id = self.env.context.get('fsm_task_id')
        if task_id:
            grouped_lines = defaultdict(lambda: self.env['sale.order.line'])
            for line in self.order_line:
                # add this for special_id filter
                special_codition =  str(kwarg.get('special_id')) in str((line.special_id,'')) if kwarg.get('special_id') else True

                if line.task_id.id == task_id and line.product_id.id in product_ids and special_codition:
                    grouped_lines[line.product_id] |= line
            return grouped_lines
        return super()._get_product_catalog_record_lines(product_ids, **kwarg)

    def _get_product_catalog_order_line_info(self, product_ids, child_field=False, **kwargs):
        """
        Override to return correct quantity based on special_id (bus filtering).
        When special_id is provided, return quantity from bus_quantities JSON for that bus,
        instead of the total line quantity.
        IMPORTANT: Preserve readOnly flag from parent method to avoid making products uneditable.
        """
        # Get the default order line info (includes readOnly flag)
        order_line_info = super()._get_product_catalog_order_line_info(product_ids, child_field=child_field, **kwargs)
       
        # Ensure all products have explicit boolean readOnly flag
        for product_id, info in order_line_info.items():
            if 'readOnly' not in info:
                info['readOnly'] = self._is_readonly()
            else:
                # Ensure it's a boolean, not a string or other type
                info['readOnly'] = bool(info['readOnly']) if info['readOnly'] is not None else self._is_readonly()
        
        # If special_id is provided, adjust quantities from bus_quantities JSON
        special_id = kwargs.get('special_id')
        if special_id:
            task_id = self.env.context.get('fsm_task_id')
            if task_id:
                # Parse bus names from special_id (comma-separated)
                bus_names = [b.strip() for b in str(special_id).split(',') if b.strip()]
                
                # Get all lines for this task
                task_lines = self.order_line.filtered(lambda l: l.task_id.id == task_id)
                
                # For each product in the order_line_info, adjust quantity based on bus_quantities
                for product_id, info in order_line_info.items():
                    # Find lines for this product
                    product_lines = task_lines.filtered(lambda l: l.product_id.id == product_id)
                    
                    # Preserve readOnly flag BEFORE making any changes
                    read_only = False
                    
                    if product_lines:
                        # Calculate total quantity from bus_quantities for the specified buses
                        total_qty_for_buses = 0
                        for line in product_lines:
                            bus_qty_dict = line.bus_quantities or {}
                            for bus_name in bus_names:
                                if bus_name in bus_qty_dict:
                                    total_qty_for_buses += bus_qty_dict[bus_name]
                        
                        # Update ONLY the quantity, preserve all other fields including readOnly
                        if total_qty_for_buses > 0:
                            info['quantity'] = total_qty_for_buses
                        else:
                            # No quantity for this bus, set to 0
                            info['quantity'] = 0
                    
                    # Always preserve readOnly flag (restore it if it was overwritten)
                    # Ensure it's explicitly a boolean, not None or other falsy value
                    info['readOnly'] = bool(read_only) if read_only is not None else False
                   
        return order_line_info     
       
    def _update_order_line_info(self, product_id, quantity, **kwargs):
        """ Update sale order line information for a given product or create a
        new one if none exists yet.
        :param int product_id: The product, as a `product.product` id.
        :return: The unit price of the product, based on the pricelist of the
                 sale order and the quantity selected.
        :rtype: float
        """
        request.update_context(catalog_skip_tracking=True)
        
        # Get task from context to access special_id (bus details)
        task_id = self.env.context.get('fsm_task_id')
        task = self.env['project.task'].browse(task_id) if task_id else False
        context_special_id = kwargs.get('special_id') or (task.current_special_id if task else None)
      
        def append_special_id(line):
            """
            Append bus name with servicing date to special_id field.
            Format: YYYY-MM-DD|bus1,bus2;YYYY-MM-DD|bus3,bus4
            Groups buses by servicing date for hierarchical display.
            """
            if not context_special_id:
                return

            # Use today's date + 3 days for new bus entries (buses are grouped by when they're added)
            today_date = fields.Date.today() + timedelta(days=3)
            if isinstance(today_date, datetime):
                date_str = today_date.strftime('%Y-%m-%d')
            elif isinstance(today_date, str):
                date_str = today_date
            else:
                date_str = str(today_date)
            
            # Parse existing bus data: format is "DATE|bus1,bus2;DATE|bus3"
            bus_data = {}
            if line.special_id:
                for entry in line.special_id.split(';'):
                    if '|' in entry:
                        date_key, buses_str = entry.split('|', 1)
                        bus_data[date_key.strip()] = [b.strip() for b in buses_str.split(',') if b.strip()]
            
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
            
            if updated_parts:
                line.write({'special_id': ';'.join(updated_parts)})
        
        sol = self.order_line.filtered(lambda line: line.product_id.id == product_id)
        if sol:
            if quantity != 0:
                sol.product_uom_qty = quantity
                # Append special_id (bus details) to existing line
                if task_id and context_special_id:
                    append_special_id(sol)
            elif self.state in ['draft', 'sent']:
                price_unit = self.pricelist_id._get_product_price(
                    product=sol.product_id,
                    quantity=1.0,
                    currency=self.currency_id,
                    date=self.date_order,
                    **kwargs,
                )
                sol.unlink()
                return price_unit
            else:
                sol.product_uom_qty = 0
        elif quantity > 0:
            # Create new sale order line
            create_vals = {
                'order_id': self.id,
                'product_id': product_id,
                'product_uom_qty': quantity,
                'sequence': ((self.order_line and self.order_line[-1].sequence + 1) or 10),  # put it at the end of the order
            }
            # Add task_id if available from context
            if task_id:
                create_vals['task_id'] = task_id
                # Set fsm_month if task exists
                if task:
                    create_vals['fsm_month'] = fields.Date.today().month
                    create_vals['last_updated_date'] = fields.Date.today()
            
            sol = self.env['sale.order.line'].create(create_vals)
            # Append special_id (bus details) to newly created line
            if task_id and context_special_id:
                append_special_id(sol)
        
        return sol.price_unit * (1-(sol.discount or 0.0)/100.0)        

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    
        