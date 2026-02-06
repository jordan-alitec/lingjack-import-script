from odoo import models, fields, api
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fax = fields.Char(string='Fax')
    customer_category_id = fields.Many2one('customer.category', string="Customer Category")

    credit_limit = fields.Float(string='Credit Limit',tracking=True)
    use_partner_credit_limit = fields.Boolean( string="Partner Limit", tracking=True)
    credit_limit_access = fields.Boolean( string="Credit Access",compute='_compute_credit_limit_access' )

    limit_balance = fields.Monetary(string='Limit Balance', compute='_compute_limit_balance',currency_field='currency_id')
    not_due = fields.Monetary(string='Not Due', compute='_compute_not_due',currency_field='currency_id',store=True)
    vendor_rating = fields.Html(string="Vendor Rating")
    sales_remark = fields.Html(string="Sales Remarks")
    account_remark = fields.Html(string="Account Remarks")
    is_share_contact = fields.Boolean(string="Share Contact")

    project_limit = fields.Monetary(string="Project Limit",currency_field='currency_id')
    account_limit = fields.Monetary(string="Account Limit",currency_field='currency_id')
    bad_debt = fields.Boolean(string="Bad Debt")


    supplies_sticker = fields.Selection(
        selection=[
            ('no', 'No Sticker Required'),
            ('written', 'Written Sticker'),
            ('blank', 'Blank Sticker')
        ],
        string='Supplies Sticker',
        help='Select the type of supplies sticker required.'
    )

    hose_reel_sticker = fields.Selection([('sticker', 'Require Sticker'),('bracket', 'Require Mounting Bracket'), ('both', 'Require Sticker & Mounting Bracket')], string="Hosereel Sticker & MB")

    def _compute_credit_limit_access(self):
        for partner in self:
            credit_limit_access = False
            if self.env.user.has_group('account.group_account_invoice'):
                credit_limit_access = True
            partner.credit_limit_access = credit_limit_access


    @api.depends('credit_limit', 'total_due')
    def _compute_limit_balance(self):
        for partner in self.sudo():
            try:
                credit_limit = partner.credit_limit if not partner.credit_limit_access else partner.credit_limit
                partner.limit_balance = (credit_limit or 0.0) - (partner.total_due or 0.0)
            except AccessError:
                partner.limit_balance = 0.0


    @api.depends('total_due', 'total_overdue')
    def _compute_not_due(self):
        for partner in self:
            partner.not_due = (partner.total_due or 0.0) - (partner.total_overdue or 0.0)



class CustomerCategory(models.Model):
    _name = 'customer.category'
    _description = 'Customer Category'

    name = fields.Char(string='Customer Category', required=True)
    company_ids = fields.Many2many('res.company', string='Companies')