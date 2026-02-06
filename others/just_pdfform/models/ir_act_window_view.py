from odoo import api, fields, models, _


class IrActionsActWindowView(models.Model):
    _inherit = 'ir.actions.act_window.view'

    view_mode = fields.Selection(
        selection_add=[('pdfForm', 'PDF Form')],
        ondelete={'pdfForm': 'cascade'},
    )

class myCompanyPartner(models.Model):
    _inherit = 'sale.order'

    myCompany = fields.Many2one(related='company_id.partner_id', string='My Company', store=False, readonly=True)
    saleSigner = fields.Char('Sale Signer')

class clearOldtemplate(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def checkUnlink(self, id):
        records = self.env['ir.attachment'].search([('res_id', '=', id),('res_model', '=', 'ir.ui.view')])
        if records:
            records.unlink()