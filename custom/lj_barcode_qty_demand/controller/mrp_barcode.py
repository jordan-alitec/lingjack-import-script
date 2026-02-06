# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import ast
from odoo import http
from odoo.http import request
from odoo.addons.stock_barcode_mrp.controllers.stock_barcode import MRPStockBarcode

_logger = logging.getLogger(__name__)


class MRPStockSFPPickingBarcode(MRPStockBarcode):

    def _try_open_production(self, barcode):
        """
        If barcode represents a production order, open the relevant SFP pickings instead.
        - Uses production_ids (Many2many) link if available.
        - If multiple SFP pickings found → open list view
        - If single picking found → open form view
        """
        
        if not barcode.startswith('mo:'):
            return False

        barcode = barcode.split(':', 1)[1]
        production = request.env['mrp.production'].search([
            ('name', '=', barcode),
        ], limit=1)


        if not production:
            return False

        try:
            sfp_pickings = request.env['stock.picking']

            try:
                sfp_pickings = request.env['stock.picking'].search([
                    ('group_id', 'ilike', production.procurement_group_id.id),
                    ('picking_type_id.code', '=', 'internal'),
                    ('name', 'ilike', 'SFP'),
                ])
            except Exception as e:
                _logger.debug(f"Approach 1 (production_ids) failed: {e}")
 

            if sfp_pickings:
                

                # Always get dict safely
                action = request.env.ref('stock.action_picking_tree_all').sudo().read()[0]

                # Ensure context is dict
                ctx = action.get('context', {}) or {}
                if isinstance(ctx, str):
                    try:
                        ctx = ast.literal_eval(ctx)
                    except Exception:
                        ctx = {}

                # Single picking → form view
                if len(sfp_pickings) == 1:
                    return self._try_open_picking(sfp_pickings.name)
                else:
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
                    domain = [('id', 'in', sfp_pickings.ids)]
                    action['domain'] = domain
                    return {'action': action}


        

            else:
                _logger.warning(f"No SFP pickings found for production {production.name}")
                return False

        except Exception as e:
            _logger.warning(f"Error opening SFP pickings for production {production.name}: {str(e)}")
            return False
