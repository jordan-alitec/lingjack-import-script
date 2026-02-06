from odoo import api, models, _ , fields, Command
from odoo.exceptions import UserError, ValidationError
import logging


_logger = logging.getLogger(__name__)
class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    state = fields.Selection(
        selection_add=[("merge", "Merged"), ("close", "Closed")],
        ondelete={"merge": "set cancel", "close": "set cancel"},
        no_copy=True,
    )

    is_closed = fields.Boolean(string='Is Closed', default=False)
    is_merged = fields.Boolean(string='Is Merged', default=False)


    def action_lj_mark_mo_done(self):
        self.ensure_one()
        wo_id = self.env.context.get('active_workorder_id')
        if not wo_id:
            raise UserError(_("Missing active work order context."))
        wo = self.env['mrp.workorder'].browse(wo_id)
        if not wo or wo.production_id.id != self.id:
            raise ValidationError(_("Invalid work order for this MO."))
        if not wo.is_last_station_for_production:
            raise ValidationError(_("You can only mark done from the last station."))
        if not wo.can_user_mark_done:
            raise ValidationError(_("You are not allowed to mark this MO done."))

        # remaining_prev = self.workorder_ids.filtered(lambda w: w.state not in ('done', 'cancel') and w.sequence < wo.sequence)
        # if remaining_prev:
        #     raise ValidationError(_("Previous work orders are not completed yet."))

        return self.button_mark_done()


    def _get_consumption_issues(self):
        '''
        Override to skip consumption issues check
        Lingjack dont want to let the operator bother ab outh this, they will unlock and edit afterward
        '''
        return False
       

    def action_merge(self):
        res = super().action_merge()

        # The result might be an action or a recordset
        merged_productions = self.browse(self.ids).exists()  # refresh current
        if not merged_productions:
            # If they got deleted/merged into another, `handle differently
            if isinstance(res, dict) and res.get('res_id'):
                merged_productions = self.browse(res['res_id'])
            else:
                 return res

        merged_productions.write({'is_merged': True})
        return res

    def action_close(self):
        for rec in self:
            if rec.state not in ['draft', 'confirmed']:
                raise ValidationError(_("You can only close a MO in draft or confirmed state."))
            rec._action_cancel()
            rec.write({'is_closed': True})

    @api.depends('move_raw_ids.state', 'move_finished_ids.state', 'workorder_ids.state', 'qty_producing', 'is_merged', 'is_closed')
    def _compute_state(self):
        """Preserve 'merge' and 'close' states and delegate other logic to base compute."""
    

        special_productions = self.filtered(lambda p: p.is_merged or p.is_closed)
        normal_productions = self.filtered(lambda p: not p.is_merged and not p.is_closed)

        if normal_productions:
            super(MrpProduction, normal_productions)._compute_state()

        # Restore special states after recompute
        for rec in special_productions:
            rec.state = 'merge' if rec.is_merged else 'close' # reassign same state to bypass overwrite
            
class StockRule(models.Model):
        _inherit = 'stock.rule'

        def _run_manufacture(self, procurements):
            """
            Override to skip manufacturing for:
            - Products that are stock items, OR
            - Rework MOs with the same product as the original MO.
            """
            MrpProduction = self.env['mrp.production']
            valid_procurements = []

            for procurement, rule in procurements:
                product = procurement.product_id

                # Efficiently find related MO (use origin_name or external ID if available)
                origin_mo = MrpProduction.search([('name', '=', procurement.origin)], limit=1)

                # Skip if no origin MO found (defensive)
                if not origin_mo:
                    valid_procurements.append((procurement, rule))
                    continue

                # Non-rework MOs always valid
                if not origin_mo.is_rework:
                    valid_procurements.append((procurement, rule))
                    continue

                # Rework MOs only valid if product differs from original MO
                if origin_mo.product_id.id != product.id:
                    valid_procurements.append((procurement, rule))

            return super()._run_manufacture(valid_procurements)
