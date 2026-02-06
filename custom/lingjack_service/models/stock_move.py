from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.http import request
from collections import defaultdict
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'


    @api.constrains('sale_line_id', 'picking_id')
    def _update_lot_from_sale_line_id(self):
        for move in self:
            if move.sale_line_id and move.picking_id:
                move.sale_line_id._update_move_lines_from_control_tag_json()
                move.sale_line_id._update_move_descriptions_from_bus_quantities()
        return


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'


    def _create_control_tag(self,invoice_id=False):
        '''
        This method is used to create a control tag record when the stock move line is validated.
        Direct creating the control tag record
        '''
        for line in self:
            if line.picking_id.company_id.fsm_control_tag_product_id and line.picking_id.company_id.fsm_control_tag_product_id == line.product_id:
                self.env['control.tag'].create({
                    'invoice_id': invoice_id,
                    'move_line_id': line.id,
                    'serial_id': line.lot_id.id,
                })
       