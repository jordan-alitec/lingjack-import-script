from odoo import api, fields, models


class SetscoSerialMoveLineHistory(models.Model):
    _name = 'setsco.serial.move.line.history'
    _description = 'SETSCO Serial Move Line History'
    _order = 'date desc, id desc'

    setsco_serial_id = fields.Many2one(
        'setsco.serial.number',
        string='Setsco Serial',
        required=True,
        index=True,
        ondelete='cascade',
    )
    move_line_id = fields.Many2one(
        'stock.move.line',
        string='Move Line',
        index=True,
        ondelete='set null',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Picking',
        index=True,
        ondelete='set null',
    )
    picking_type_code = fields.Selection(
        selection=[
            ('incoming', 'Incoming'),
            ('outgoing', 'Outgoing'),
            ('internal', 'Internal'),
        ],
        string='Picking Type',
        index=True,
    )
    event = fields.Selection(
        selection=[
            ('assigned', 'Assigned'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Event',
        required=True,
        default='done',
        index=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            'uniq_setsco_serial_move_line_event',
            'unique(setsco_serial_id, move_line_id, event)',
            'Duplicate SETSCO history entry for the same serial, move line, and event.',
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Populate picking_id/type from move_line_id if missing."""
        for vals in vals_list:
            ml_id = vals.get('move_line_id')
            if ml_id and (not vals.get('picking_id') or not vals.get('picking_type_code')):
                ml = self.env['stock.move.line'].browse(ml_id)
                if ml.exists() and ml.picking_id:
                    vals.setdefault('picking_id', ml.picking_id.id)
                    if ml.picking_id.picking_type_id:
                        vals.setdefault('picking_type_code', ml.picking_id.picking_type_id.code)
        return super().create(vals_list)

