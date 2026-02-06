from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)
class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    month_used = fields.Char(string='Month Used', size=2, help="The last month the sequence was used")


    def _next(self, sequence_date=None):
        # Get the current month as a string (e.g. '11')
        current_month = datetime.now().strftime('%m')

        sequence = self.sudo()
        if sequence and '%(month)s' in (sequence.prefix or ''):
            # If month changed, reset number and update month_used
            if sequence.month_used != current_month:
                sequence.write({
                    'month_used': current_month,
                    'number_next_actual': 1
                })

        return super(IrSequence, sequence)._next(sequence_date)

