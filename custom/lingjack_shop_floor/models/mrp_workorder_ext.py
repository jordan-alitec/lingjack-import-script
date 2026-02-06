from odoo import api, fields, models, _


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    is_last_station_for_production = fields.Boolean(
        compute='_compute_is_last_station_for_production',
        help='True if this work order is the last station for its MO.'
    )
    can_user_mark_done = fields.Boolean(
        compute='_compute_can_user_mark_done',
        help='True if the current user can mark the MO done from this WO.'
    )

    @api.depends('production_id', 'state', 'sequence')
    def _compute_is_last_station_for_production(self):
        for wo in self:
            if not wo.production_id:
                wo.is_last_station_for_production = False
                continue
            # Filter out cancelled work orders; sequence determines last station, not id
            active_wos = wo.production_id.workorder_ids.filtered(lambda w: w.state != 'cancel')
            if not active_wos:
                wo.is_last_station_for_production = False
                continue
            # Determine last by highest sequence among active WOs
            max_seq = max(active_wos.mapped('sequence') or [wo.sequence])
            wo.is_last_station_for_production = (wo.sequence == max_seq)

    @api.depends_context('uid')
    def _compute_can_user_mark_done(self):
        for wo in self:
            wo.can_user_mark_done = self.env.user.has_group('mrp.group_mrp_user')

    def _get_fields_for_tablet(self):
        fields_list = super()._get_fields_for_tablet()
        return fields_list + ['is_last_station_for_production', 'can_user_mark_done']


