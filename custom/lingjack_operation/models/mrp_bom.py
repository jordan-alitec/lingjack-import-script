from odoo import models, api, _
from odoo.exceptions import ValidationError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.model_create_multi
    def create(self, vals_list):
        res = super(MrpBom, self).create(vals_list)
        for vals in vals_list:
            bom_type = vals.get('type', 'normal')
            user_in_group = self.env.user.has_group('lingjack_operation.group_edit_bom')

            if bom_type == 'normal' and not user_in_group:
                raise ValidationError(_("You are not allowed to create a BoM with type 'Manufacture this product'."))
        return res

    def write(self, vals):
        res = super(MrpBom, self).write(vals)
        user_in_group = self.env.user.has_group('lingjack_operation.group_edit_bom')

        for rec in self:
            new_bom_type = vals.get('type', rec.type)
            if new_bom_type == 'normal' and not user_in_group:
                raise ValidationError(_("You are not allowed to edit this BoM because it is set to 'Manufacture this product' (normal type)."))

        return res
