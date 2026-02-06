from odoo import models, fields

class QualityCheck(models.Model):
    _inherit = 'quality.check'

    po_number = fields.Char(
        string="PO Number",
        related='picking_id.origin',
        readonly=True,
        store=True
    )
    description = fields.Text(string='Description')

    def do_fail(self):
        res = super().do_fail()
        for rec in self:
            if rec.picking_id and rec.picking_id.location_dest_id:
                rec.point_id.failure_location_ids = [(4, rec.picking_id.location_dest_id.id)]
        return res

    previous_transfer = fields.Char(
        string="Previous Transfer",
        related='picking_id.previous_transfer',
        readonly=True,
        store=True
    )

    description = fields.Text(string='Description')

    def do_fail(self):
        res = super().do_fail()
        for rec in self:
            if rec.picking_id and rec.picking_id.location_dest_id:
                rec.point_id.failure_location_ids = [(4, rec.picking_id.location_dest_id.id)]
        return res


