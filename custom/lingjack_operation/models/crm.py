from odoo import models, fields

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    date = fields.Date(string="Date")
    Visit_purpose_id = fields.Many2one('crm.visit.purpose', string="Purpose Of Visit")
    remarks = fields.Html(string="Remarks")
    expected_delivery_date = fields.Date(string='Expected Delivery Date')



class CrmVisit(models.Model):
    _name = 'crm.visit.purpose'
    _description = 'Purpose of Visit'

    name = fields.Char(string='Visit Purpose', required=True)