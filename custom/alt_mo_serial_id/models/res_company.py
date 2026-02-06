# -*- coding: utf-8 -*-

from odoo import api, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        Sequence = self.env['ir.sequence']
        for company in companies:
            if not Sequence.search([('code', '=', 'production.serial'), ('company_id', '=', company.id)], limit=1):
                Sequence.create({
                    'name': 'Production Serial (company)',
                    'code': 'production.serial',
                    'company_id': company.id,
                    'prefix': '',
                    'padding': 10,
                    'number_next': 1,
                    'number_increment': 1,
                    'implementation': 'standard',
                })
        return companies
