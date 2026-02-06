from odoo import models, api


class TierValidation(models.AbstractModel):
    _inherit = "tier.validation"

    @api.model
    def _get_all_validation_exceptions(self):
        res = super()._get_all_validation_exceptions()
        res.extend(['so_status','sale_date','person_incharge_id','remarks','cs_in_charge_id','cs_note','so_price_category','sales_comment','finance_comment','management_comment','customer_signature','signature_name','signature_date','delivered_by','driver_picking_date','remarks','driver_status','note'])
        return res
