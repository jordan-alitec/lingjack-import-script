from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import ValidationError


class StockReturnPickingLine(models.TransientModel):
    _inherit = 'stock.return.picking.line'

    @api.constrains('quantity')
    def _check_quantity_not_exceed_move(self):
        by_pass = self.env.context.get('by_pass', False)
        if by_pass:
            return

        for record in self:
            if record.quantity > record.move_id.product_qty:
                raise ValidationError(
                    "Return quantity cannot exceed the original move quantity. "
                    f"Maximum allowed: {record.move_id.product_qty}"
                )