from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    next_reminder_execution_date = fields.Datetime(string="Reminder Execution Date")
    
    password_expiration = fields.Integer(config_parameter="auth_password_policy.password_expiration", default=0)
    
    password_history = fields.Integer(config_parameter="auth_password_policy.password_history", default=0)
    password_lower = fields.Integer(config_parameter="auth_password_policy.password_lower", default=0)
    password_upper = fields.Integer(config_parameter="auth_password_policy.password_upper", default=0)
    password_numeric = fields.Integer(config_parameter="auth_password_policy.password_numeric", default=0)
    password_special = fields.Integer(config_parameter="auth_password_policy.password_special", default=0)
    test_password_expiration = fields.Boolean(
        "Test password expiration", config_parameter="auth_password_policy.test_password_expiration", default=False,
        help="If check it, time unit of password_expiration will be converted from days to minutes"
    )
    minimum_reset_interval = fields.Integer(
        string="Minimum Reset Interval (hours)", config_parameter="auth_password_policy.minimum_reset_interval", default=0,
        readonly=False )

    # time_compute_expire = fields.Float(config_parameter="auth_password_policy.time_compute_expire", default=0)
    day_alert_expire = fields.Integer(config_parameter="auth_password_policy.day_alert_expire", default=0)


    @api.model_create_multi
    def create(self, vals_list):
        record = super(ResConfigSettings, self).create(vals_list)
        record.update_cron()
        return record

    def write(self, vals):
        res = super(ResConfigSettings, self).write(vals)
        self.update_cron()
        return res
    

    def update_cron(self):
        cron = self.env.ref('zehntech_password_security.ir_cron_send_email_password_expire')
        if self.next_reminder_execution_date:
             cron.write({
            'nextcall': self.next_reminder_execution_date,
        })
             
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['minimum_reset_interval'] = self.env['ir.config_parameter'].sudo().get_param('minimum_reset_interval', default=False)
        return res

    @api.model
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('minimum_reset_interval', self.minimum_reset_interval)         

   
    @api.constrains('password_expiration', 'day_alert_expire')
    def _check_password_expiration_alert(self):
        for rec in self:
            # Check for non-negative values
            if rec.password_expiration < 0:
                raise ValidationError(_("Password Expiration Period (days) must be non-negative values."))

            if rec.day_alert_expire < 0:
                raise ValidationError(_("Expiration Alert Period (days) must be non-negative values."))
               
            # Check that alert period does not exceed expiration period
            if rec.day_alert_expire > rec.password_expiration:
                raise ValidationError(_("Expiration Alert Period (days) must be less than the Password Expiration Period (days)"))   

            # Check that values are within 365-day limit
            if rec.password_expiration >= 365:
                raise ValidationError(_("You can only choose days within 365 days (1 year) for Password Expiration Period (days)"))

            if rec.day_alert_expire >= 365:
                raise ValidationError(_("You can only choose days within 365 days (1 year) for Expiration Alert Period (days)."))
            
    @api.constrains('password_lower', 'password_upper','password_numeric','password_special','minimum_reset_interval','password_history','minlength')
    def _check_password_required_characters(self):
        for rec in self:
            # Check for non-negative values
            if rec.password_lower < 0:
                raise ValidationError(_("Lowercase Characters must be non-negative values."))

            if rec.password_upper < 0:
                raise ValidationError(_("Uppercase Characters must be non-negative values."))
                      
            if rec.password_numeric < 0:
                raise ValidationError(_("Numeric Characters must be non-negative values.")) 

            if rec.password_special < 0:
                raise ValidationError(_("Special Characters must be non-negative values."))  

            if rec.minlength < 0:
                raise ValidationError(_("Minimum Password Length Characters must be non-negative values."))

            if rec.minlength < 8:
                raise ValidationError(_("Minimum Password Length Characters must be greater than 8."))
            if rec.minlength > 20:
                raise ValidationError(_("Minimum Password Length Characters must be less than 20."))

            if rec.minimum_reset_interval < 0:
                raise ValidationError(_("Minimum Reset Interval (hours) must be non-negative values."))

             # Ensure maximum values do not exceed limits
            if rec.password_lower > 10:
                raise ValidationError(_("Minimum Lowercase Characters cannot be greater than 10."))
            

            if rec.password_upper > 10:
                raise ValidationError(_("Minimum Uppercase Characters cannot be greater than 10."))

            if rec.password_numeric > 10:
                raise ValidationError(_("Minimum Numeric Characters cannot be greater than 10."))

            if rec.password_special > 10:
                raise ValidationError(_("Minimum Special Characters cannot be greater than 10."))

            if rec.minimum_reset_interval >= 25:
                raise ValidationError(
                    _("Minimum Reset Interval (hours) must be less than/equal to 24 hours.")
                )
            if rec.password_history < 0:
                raise ValidationError(_("Disallow reuse of previous passwords must be non-negative values."))
            if rec.password_history > 20:
                raise ValidationError(_("Disallow reuse of previous passwords must be less than 20."))
            
    @api.constrains('minlength', 'password_lower', 'password_upper', 'password_numeric', 'password_special')
    def _check_minimum_character_length(self):
     for rec in self:
        # Calculate the total required minimum characters
        total_required = rec.password_lower + rec.password_upper + rec.password_numeric + rec.password_special

        # Ensure the minimum length is not less than the sum of individual requirements
        if rec.minlength < total_required:
            raise ValidationError(_("Minimum Password Length Characters (%d) cannot be less than the total of individual requirements of [Minimum Lowercase Characters, Minimum Uppercase Characters, Minimum Numeric Characters, Minimum Special Characters]  (%d).") % (rec.minlength, total_required))