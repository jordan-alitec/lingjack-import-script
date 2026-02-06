
from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    ac_picking_ids = fields.One2many('stock.picking', 'invoice_id', string="Picking References")
    ac_picking_count = fields.Integer('Picking Count', compute='_compute_picking_count')

    def _compute_picking_count(self):
        for rec in self:
            rec.ac_picking_count = len(rec.ac_picking_ids)

    def button_cancel(self):
        super(AccountMove, self).button_cancel()

        picking_force_unlink = self.env.context.get('picking_force_unlink', False)
        if picking_force_unlink:
            self._unlink_picking()
            return

        invoice_with_picking_ids = self.filtered(lambda r: r.move_type == 'out_invoice' and len(r.ac_picking_ids) > 0)
        if len(invoice_with_picking_ids) == 0:
            return

        vals = {'invoice_ids': [(4, rec.id, 0) for rec in invoice_with_picking_ids]}
        wiz_id = self.env['wiz.confirm.unlink.picking.from.invoice'].create(vals)
        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'wiz.confirm.unlink.picking.from.invoice',
            'views': [(False, 'form')],
            'target': 'new',
            'res_id': wiz_id.id
        }
        return action

    def _unlink_picking(self):
        picking_ids = self.mapped('ac_picking_ids')
        picking_ids.write({'invoice_id': False,
                           'invoice_state': '2binvoiced'})


