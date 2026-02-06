from odoo import models, fields

class ConfirmExportControlWizard(models.TransientModel):
    _name = 'confirm.export.control.wizard'
    _description = 'Confirm Export Control Item Wizard'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)

    def confirm_action(self):
        self.sale_order_id.with_context(no_open_export_wizard=True).action_confirm()
        return {'type': 'ir.actions.act_window_close'}
