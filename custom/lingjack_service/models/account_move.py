from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    control_tag_count = fields.Integer(
        string='Control Tags',
        compute='_compute_control_tag_count',
    )

    def _compute_control_tag_count(self):
        for move in self:
            if not self.env.user.has_group('lingjack_service.group_control_tag'):
                move.control_tag_count = 0
                continue
            move.control_tag_count = self.env['control.tag'].search_count([
                ('invoice_id', '=', move.id),
            ])

    def action_view_control_tag(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Control Tags',
            'res_model': 'control.tag',
            'view_mode': 'list',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id},
        }

    def _unlink_picking(self):
        res = super()._unlink_picking()

        control_tags = self.env['control.tag'].search([
            ('invoice_id', 'in', self.ids)
        ])
        control_tags.unlink()
        return res