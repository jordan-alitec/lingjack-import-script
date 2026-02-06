from odoo import models, fields, api, _


class DistributionSettings(models.Model):
    _name = 'distribution.settings'
    _description = 'Distribution Record Settings'
    _rec_name = 'company_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10, help='Determines the order of settings. Lower numbers have higher priority.')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    # CoC Holder Information
    coc_holder_name = fields.Char(string='CoC Holder Name', required=True, tracking=True)
    coc_holder_acra_uen = fields.Char(string='CoC Holder ACRA UEN', required=True, tracking=True)
    coc_reference_number = fields.Char(string='CoC Reference Number', required=True, tracking=True)
    
    # Local Representative Information
    local_representative_name = fields.Char(string='Local Representative Name', required=True, tracking=True)
    local_representative_acra_uen = fields.Char(string='Local Representative ACRA UEN', required=True, tracking=True)
    
    # Certificate Information
    certificate_no = fields.Char(string='Certificate No', required=True, tracking=True)
    coc_expired_date = fields.Date(string='CoC Expired Date', required=True, tracking=True)
    coc_issue_date = fields.Date(string='CoC Issue Date', required=True, tracking=True)
    
    # Additional Information
    active = fields.Boolean(string='Active', default=True, tracking=True)
    notes = fields.Text(string='Notes', tracking=True)
    
    # Computed field for display name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    # def name_get(self):
    #     """Display name shows CoC Reference Number"""
    #     result = []
    #     for record in self:
    #         name = f"{record.coc_reference_number}"
    #         if record.coc_holder_name:
    #             name += f" - {record.coc_holder_name}"
    #         result.append((record.id, name))
    #     return result

    @api.depends('coc_reference_number')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.coc_reference_number}"

    @api.model
    def get_settings(self):
        """Get the active settings for the current company with highest priority (lowest sequence) and not expired"""
        today = fields.Date.today()
        return self.search([
            ('company_id', '=', self.env.company.id), 
            ('active', '=', True),
            ('coc_expired_date', '>=', today)  # Only non-expired settings
        ], order='sequence, id', limit=1) 