from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DriverIncompleteWizard(models.TransientModel):
    _name = 'driver.incomplete.wizard'
    _description = 'Driver Delivered Incomplete Wizard'

    picking_id = fields.Many2one('stock.picking', required=True)
    remarks = fields.Text(string="Remarks", required=True)

    def action_confirm(self):
        self.ensure_one()

        if not self.remarks:
            raise ValidationError(_("Remarks is required for Incomplete Delivery."))

        self.picking_id.sudo().write({
            'driver_status': 'delivered_incomplete',
            'remarks': self.remarks,
            'delivered_by': self.env.user.id,
            'driver_picking_date': fields.Datetime.now(),
        })

