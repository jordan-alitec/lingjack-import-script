# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    sh_backdate = fields.Date("BackDate")
    remarks_for_inventory_adj = fields.Text(string = "Remarks for Backdate")
    is_remark_mandatory = fields.Boolean(related="company_id.remark_mandatory_for_inventory_adj")

    @api.model
    def _get_inventory_fields_write(self):
        # Returns a list of fields user can edit when he want to edit a quant in `inventory_mode`.

        res = super()._get_inventory_fields_write()
        res += ['sh_backdate','remarks_for_inventory_adj']
        return res

    def write(self, vals):
        """
        The function updates the 'inventory_date' field in the record with a backdated value if a
        specific context key is present.
        """
        if vals.get('inventory_date') and self.env.context.get('sh_backdate'):
            vals['inventory_date'] = self.env.context.get('sh_backdate')
        return super().write(vals)

    def _apply_inventory(self):
        """
        The function `_apply_inventory` processes inventory adjustments for stock quantities, including
        handling backdated quantities.
        """
        if not self.env.company.backdate_for_inventory_adj:
            return super()._apply_inventory()
        backdate_quant = self.filtered(lambda x: x.sh_backdate)
        if backdate_quant:
            for quant in backdate_quant:
                super(StockQuant,quant.with_context(sh_backdate = quant.sh_backdate,sh_backdate_remark=quant.remarks_for_inventory_adj))._apply_inventory()
                quant.inventory_date = quant.sh_backdate
        super(StockQuant,self-backdate_quant)._apply_inventory()
