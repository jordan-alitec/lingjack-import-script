# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import ast
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController


class LingjackStockBarcode(StockBarcodeController):

    def _try_open_picking(self, barcode):
        """ If barcode represents a picking, open it
        """
      
        corresponding_picking = request.env['stock.picking'].search([
            ('name', '=', barcode),
        ], limit=1)
        _logger.warning(f'corresponding_picking: {corresponding_picking}')

        if corresponding_picking:
            next_transfers = corresponding_picking._get_next_transfers()
            _logger.warning(f'next_transfers: {next_transfers.mapped}')
            if next_transfers and len(next_transfers) == 1:
                action = next_transfers.action_open_picking_client_action()
                return {'action': action}
            elif next_transfers and len(next_transfers) > 1:
                # Multiple pickings → open a standard act_window in kanban first
                action = request.env.ref('stock_barcode.stock_picking_action_kanban').sudo().read()[0]
                # Normalize the domain
                domain = action.get('domain', [])
                if isinstance(domain, str):
                    try:
                        import ast
                        domain = ast.literal_eval(domain)
                    except Exception:
                        domain = []

                # Merge with your new condition
                domain = [('id', 'in', next_transfers.ids)]
                action['domain'] = domain
                return {'action': action}

            else:
                action = corresponding_picking.action_open_picking_client_action()
                return {'action': action}   
        return False

class BarcodeLocationController(http.Controller):

    @http.route('/web/load/location/by_barcode', type='json', auth='user')
    def load_location_by_barcode(self, rawBarcode=None, picking_id=None, location_type='source', **kw):
        """
        Scans barcode → finds location → updates picking and its move_line_ids.
        location_type: 'source' -> location_id
                       'destination' -> location_dest_id
        Returns:
            { success: True/False, location: {id,name,barcode}, written_field: 'Location'|'Destination Location'|'none', error? }
        """
        if not rawBarcode:
            return {'success': False, 'error': 'Barcode cannot be empty'}

        cleaned = rawBarcode.strip()
        Location = request.env['stock.location'].sudo()
        location = Location.search([('barcode', '=', cleaned)], limit=1)
        if not location:
            return {'success': False, 'error': f"No location found for barcode: {cleaned}"}

        location_data = {'id': location.id, 'name': location.name, 'barcode': location.barcode}

        # if picking_id provided - try to update picking and its move lines
        if picking_id:
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'success': False, 'error': f"Picking {picking_id} not found", 'location': location_data}

            # decide single field to write and friendly label
            vals = {}
            if location_type in ('source'):
                vals['location_id'] = location.id
                written_field = 'Location'
            elif location_type in ('destination'):
                vals['location_dest_id'] = location.id
                written_field = 'Destination Location'
            else:
                return {'success': False, 'error': f"Unknown location_type: {location_type}", 'location': location_data}

            try:
                if vals:
                    picking.sudo().write(vals)
                    if picking.move_line_ids:
                        picking.move_line_ids.sudo().write(vals)
                return {'success': True, 'location': location_data, 'written_field': written_field}
            except Exception as e:
                return {'success': False, 'error': f"Error updating picking: {str(e)}", 'location': location_data}

        # no picking_id provided: just return found location
        return {'success': True, 'location': location_data, 'written_field': 'none'}