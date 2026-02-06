from odoo import api, fields, models


class WizConfirmUnlinkPickingFromInvoice(models.TransientModel):
    _name = 'wiz.confirm.unlink.picking.from.invoice'
    _description = 'Confirm Unlink Pickings from Invoice'

    invoice_ids = fields.Many2many('account.move', string='Invoices')

    def action_confirm(self):
        self.invoice_ids._unlink_picking()
        return
