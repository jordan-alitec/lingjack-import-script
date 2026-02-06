from odoo import models, fields, _
from odoo.exceptions import UserError

class StockPickingAttachmentWizard(models.TransientModel):
    _name = 'stock.picking.attachment.wizard'
    _description = 'Add Attachments to Picking'

    picking_id = fields.Many2one(
        'stock.picking',
        string='Picking',
        required=True,
        readonly=True
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        required=True
    )

    def action_add_attachments(self):
        self.ensure_one()

        if not self.attachment_ids:
            raise UserError(_("Please upload at least one file."))

        self.attachment_ids.sudo().write({
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
        })

        return {'type': 'ir.actions.act_window_close'}
