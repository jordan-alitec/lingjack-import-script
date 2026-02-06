from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    old_picking = fields.Integer(string='Old Picking ID')

    @api.model
    def api_create_purchase_receive_order(self, groups):
        company = groups.get('company_id')
        company_id = self.env['res.company'].browse(company)

        grn_number = groups.get("grn_number")
        po_number = groups.get("purchase_order_number")
        rows = groups.get("rows", [])


        if not po_number:
            raise UserError(f"Purchase Order number missing for GRN {grn_number}")

        # Find the cancelled incoming picking linked to this PO
        cancelled_pickings = self.env["stock.picking"].with_company(company_id).search([
            ("origin", "=", po_number),
            ("picking_type_code", "=", "incoming"),
            ("state", "=", "cancel")
        ], limit=1)

        if not cancelled_pickings:
            return False

        receive_date_str = rows[0].get("date") if rows else None
        receive_date = False
        if receive_date_str:
            try:
                receive_date_str = receive_date_str.split('.')[0]
                receive_date = fields.Datetime.to_datetime(receive_date_str)
            except Exception as e:
                _logger.warning(f"Invalid date format in GRN {grn_number}: {receive_date_str} ({e})")

        old_picking = cancelled_pickings[0]
        new_picking_name = grn_number

        existing_picking = self.env["stock.picking"].search([("name", "=", grn_number)], limit=1)
        if existing_picking:
            new_picking = existing_picking
        else:
            # Duplicate the cancelled picking
            new_picking = old_picking.copy({
                'state': 'draft',
                'old_picking': old_picking.id,
                'name': new_picking_name,
                'scheduled_date': receive_date or fields.Datetime.now(),
                'move_ids_without_package': [],
            })
            new_picking.move_ids_without_package.filtered(lambda m: m.product_uom_qty == 0).unlink()

        move_map = []
        for move in new_picking.move_ids_without_package:
            old_purchase_line = move.purchase_line_id.old_purchase_order_line
            if old_purchase_line:
                move_map.append((old_purchase_line, move.id))
        move_map = dict(move_map)

        for row in rows:
            qty = row.get("received.qty", 0)
            old_move = row.get('purchase.receive.line.id', 0)
            if qty == 0:
                continue
            old_purchase_line = row.get('purchase.line.id', None)
            if not old_purchase_line:
                continue

            move = move_map.get(old_purchase_line, None)
            if move:
                move_id = self.env['stock.move'].browse(move)
                vals = {
                    'product_uom_qty': qty,
                    'old_move': old_move,
                }
                move_id.write(vals)
        new_picking.action_confirm()

        return {
            "status": "success",
            "new_picking_id": new_picking.id,
            "old_picking_id": old_picking.id,
            "grn_number": grn_number,
            "po_number": po_number,
        }


    @api.model
    def api_create_return(self, dct):
        """
        Create a return picking from a dictionary input.
        The dictionary should contain the following keys:
        - 'return_name': Name of the return picking to create
        - 'picking_name': name of the original picking to return from
        - 'company_id': ID of the company
        - 'move_lines': List of dictionaries, each containing:
            - 'product_code': internal reference of the product to return
            - 'quantity': Quantity of the product to return
            - 'origin_return_move': Old move ID from the stock.move that is being returned
        - 'scheduled_date': (Optional) Scheduled date for the return picking
        """

        # 1. Identify Original Picking using old_move (origin_return_move)
        # Extract all legacy move IDs from the request
        old_move_ids = [line.get('origin_return_move') for line in dct.get('move_lines', []) if line.get('origin_return_move')]
        
        if not old_move_ids:
             return f"No origin_return_move provided in move_lines for {dct.get('return_name')}."

        # Search for corresponding stock moves in Odoo
        # We search for moves that have 'old_move' in our list and belong to the correct company
        origin_moves = self.env['stock.move'].search([
            ('old_move', 'in', old_move_ids),
            ('company_id', '=', dct.get('company_id'))
        ])
        
        if not origin_moves:
             return f"No original stock moves found for origin codes: {old_move_ids}."

        # Get unique picking IDs from these moves
        found_pickings = origin_moves.mapped('picking_id')
        
        if len(found_pickings) == 0:
             return f"Stock moves found {origin_moves.ids}, but no associated picking found."
        
        if len(found_pickings) > 1:
             return f"Multiple origin pickings detected for {dct.get('return_name')}: {found_pickings.mapped('name')}. Cannot determine unique original picking."
             
        original_picking_id = found_pickings[0]

        domain = [('name', '=', dct.get('return_name')), ('company_id', '=', dct.get('company_id'))]
        existing_return = self.env['stock.picking'].search_count(domain) > 0
        if existing_return:
            return f"Return picking already exists: {dct.get('return_name')}"

        return_wizard_id = self.env['stock.return.picking'].with_context(by_pass=True).create({
            'picking_id': original_picking_id.id
        })

        unable_to_create = True

        # Build the return move dct
        return_move_dct_lst = []
        for line in dct.get('move_lines', []):
            return_quantity = line.get('quantity', 0)
            old_stock_move = line.get('origin_return_move', 0)
            origin_move_id = original_picking_id.move_ids.filtered(lambda r: r.old_move == old_stock_move)
            if not origin_move_id:
                continue

            return_move_dct_lst.append((origin_move_id.id, return_quantity))
        return_move_dct = dict(return_move_dct_lst)

        for move in return_wizard_id.with_context(by_pass=True).product_return_moves:
            return_quantity = return_move_dct.get(move.move_id.id, 0)
            move.quantity = return_quantity
            # if move.move_quantity >= return_quantity > 0:
            #     move.quantity = return_quantity
            #     unable_to_create = False

        # if unable_to_create:
        #     return -1

        return_picking_id = return_wizard_id._create_return()
        return_picking_id.scheduled_date = dct.get('scheduled_date', fields.Datetime.now())
        return_picking_id.name = dct['return_name']
        return return_picking_id.id

    @api.model
    def api_create_delivery_order(self, vals):
        """
        API method to create a delivery order by duplicating existing picking from sale order.

        :param vals: Dictionary containing delivery order values
        :return: Created delivery order record ID
        """
        _logger.info(f"Creating delivery order with values: {vals}")
        
        # 1. Find the sale order by origin name
        origin = vals.get('origin', 'Unknown Origin')
        sale_id = self.env['sale.order'].search([('name', '=', origin)], limit=1)
        if not sale_id:
            return f"Sale Order {origin} does not exist."
        
        # 2. Get the existing picking with the lowest record id
        existing_picking = self.search([
            ('sale_id', '=', sale_id.id),
            ('state', '=', 'cancel')
        ], order='id asc', limit=1)
        
        if not existing_picking:
            return f"No existing picking found for Sale Order {origin}."
        
        # Check if delivery order with this name already exists
        do_name = vals.get('name')
        if self.search_count([('name', '=', do_name), ('company_id', '=', vals.get('company_id'))]) > 0:
            return f"Delivery Order {do_name} already exists."
        
        other_for_mapping = vals.pop('other_for_mapping', {})
        move_lines = vals.pop('move_lines', [])
        scheduled_date = vals.get('scheduled_date', fields.Datetime.now())
        
        # Build move data matched to sale order lines
        move_data = []
        for line_vals in move_lines:
            product_code = line_vals.pop('product_code', None)
            sale_line_old_id = line_vals.pop('sale_line_id', False)
            
            sale_line_id = self.env['sale.order.line'].search([
                ('old_sale_order_line', '=', sale_line_old_id)
            ], limit=1) if sale_line_old_id else False
            
            if not sale_line_id:
                _logger.warning(f"Sale order line with old ID {sale_line_old_id} not found, skipping line.")
                continue
            
            move_data.append({
                'sale_line_id': sale_line_id.id,
                'product_id': sale_line_id.product_id.id,
                'product_uom_qty': line_vals.get('product_uom_qty', 0),
                'quantity': line_vals.get('quantity', 0),
                'old_move': line_vals.get('old_move', 0),
            })
        
        # Aggregate move_data by sale_line_id
        aggregated_moves = {}
        for data in move_data:
            sl_id = data['sale_line_id']
            if sl_id in aggregated_moves:
                aggregated_moves[sl_id]['product_uom_qty'] += data['product_uom_qty']
                # old_move is kept from the first entry
            else:
                aggregated_moves[sl_id] = data

        move_data = list(aggregated_moves.values())
        
        if not move_data:
            return "No valid move lines to create delivery order."
        
        # 3. Duplicate the existing picking
        new_picking = existing_picking.copy({
            'name': do_name,
            'scheduled_date': scheduled_date,
            'old_picking': vals.get('old_picking', 0),
        })
        
        # 4. Update the new record with quantities
        for data in move_data:
            # Find the corresponding move in the new picking
            new_moves = new_picking.move_ids.filtered(
                lambda m: m.sale_line_id.id == data['sale_line_id']
            )
            if new_moves:
                new_move = new_moves[0]
                new_move.write({
                    'product_uom_qty': data['product_uom_qty'],
                    'old_move': data['old_move'],
                })
            else:
                _logger.warning(f"Move for sale line {data['sale_line_id']} not found in new picking.")
        
        # Remove moves from new picking that are not in move_data
        sale_line_ids_in_data = [d['sale_line_id'] for d in move_data]
        moves_to_remove = new_picking.move_ids.filtered(
            lambda m: m.sale_line_id.id not in sale_line_ids_in_data
        )
        if moves_to_remove:
            moves_to_remove.unlink()
        
        # 5. Update the original record quantities (subtract delivered qty)
        for data in move_data:
            original_move = existing_picking.move_ids.filtered(
                lambda m: m.sale_line_id.id == data['sale_line_id']
            )
            if original_move:
                original_move = original_move[0]
                new_qty = original_move.product_uom_qty - data['product_uom_qty']
                if new_qty >= 0:
                    original_move.product_uom_qty = new_qty
                else:
                    _logger.warning(f"Original move qty would be negative for sale line {data['sale_line_id']}")
        
        new_picking.message_post(body=f"Other for Mapping: {other_for_mapping}")
        
        # Confirm the new picking
        new_picking.action_confirm()
        
        return new_picking.id

    @api.model
    def api_incoming_shipment_validate(self, company, id):
        picking_id = self.with_company(company).browse(id)
        if picking_id.state in ['done', 'cancel']:
            return [picking_id.state, f'{id} / {picking_id.name}']

        product_ids = picking_id.move_ids.mapped('product_id')
        product_with_lot_ids = product_ids.filtered(lambda p: p.tracking in ['serial', 'lot'])
        for line_id in picking_id.move_line_ids.filtered(lambda m: m.product_id in product_with_lot_ids):
            line_id.write({'lot_name': 'OPENING'})
        picking_id.button_validate()
        return [picking_id.state, f'{id} / {picking_id.name}']

    @api.model
    def api_outgoing_shipment_validate(self, company, id):
        picking_id = self.with_company(company).browse(id)

        if picking_id.state in ['done', 'cancel']:
            return [picking_id.state, f'{id} / {picking_id.name}']

        for line in picking_id.move_ids:
            line.write({'quantity': line.product_uom_qty})
        picking_id.button_validate()
        return [picking_id.state, f'{id} / {picking_id.name}']

        # if picking_id.state == 'assigned':
        #     picking_id.button_validate()
        #     return [picking_id.state, f'{id} / {picking_id.name}']
        #
        #
        #
        # # if state == 'confirmed'
        # for line in picking_id.move_ids:
        #     line.write({'quantity': line.product_uom_qty})
        # # picking_id.button_validate()
        # return [picking_id.state, f'{id} / {picking_id.name}']


class StockMove(models.Model):
    _inherit = "stock.move"

    old_move = fields.Integer(string='Old Move ID')
