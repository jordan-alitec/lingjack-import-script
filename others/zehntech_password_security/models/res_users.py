import re
import hashlib
from datetime import datetime, timedelta
from dateutil import tz
from markupsafe import Markup, escape
import pytz
from odoo import _, api, fields, models, tools, http
from odoo.exceptions import UserError, ValidationError
from odoo.addons.auth_signup.models.res_partner import SignupError, now


def delta_now(**kwargs):
    return fields.Datetime.now() + timedelta(**kwargs)

class ResUsers(models.Model):
    _inherit = "res.users"
    
    password_write_date = fields.Datetime("Last password update", default=fields.Datetime.now, readonly=True)
    next_password_write_date = fields.Datetime("Next password update", compute="_compute_next_password_write_date")
    password_history_ids = fields.One2many(
        string="Password History",
        comodel_name="res.users.pass.history",
        inverse_name="user_id",
        readonly=True,
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['password_write_date', 'next_password_write_date']
    
    def write(self, vals):
        if vals.get("password"):
            server_time = datetime.now(pytz.UTC)
            vals["password_write_date"] = fields.Datetime.to_string(server_time)


            for user in self:
                old_password_hash = user._get_old_password_hash()  # Odoo already stores hashed password
                new_password_hash = hashlib.sha256(vals["password"].encode()).hexdigest()
                self.env['user.password.log'].create({
                    'user_id': user.id,
                    'changed_by': self.env.user.id,
                    'old_password_hash': old_password_hash,
                    'new_password_hash': new_password_hash,
                    'change_date': vals["password_write_date"]
                })

        return super(ResUsers, self).write(vals)

    def _get_old_password_hash(self):
        password_log = self.env['user.password.log'].search([
            ('user_id', '=', self.id)], limit=1, order='change_date desc')
        
        if password_log:
            return password_log.new_password_hash  # This is the last known password hash
        else:
            return ""    

    def action_send_password_expire(self, user_ids=[]):
        params = self.env["ir.config_parameter"].sudo()
        password_expiration = int(params.get_param('auth_password_policy.password_expiration'))
        days_before = int(params.get_param('auth_password_policy.day_alert_expire'))

        if password_expiration <= 0:
            return

        if user_ids:
            all_users = self.env['res.users'].sudo().search([('id', 'in', user_ids)])
        else:
            all_users = self.env['res.users'].sudo().search([])

        for rec in all_users:
            if rec.notification_type != 'inbox':
                delta_days = (rec.next_password_write_date - datetime.today()).days
                if delta_days <= days_before: #This condition is checking if the number of days (delta_days) is less than or equal to days_before (which we calculated earlier). If this condition is true, it means the time has come to send a password expiry alert.
                    rec._send_notification_password_expire(delta_days)

    def _send_notification_password_expire(self, delta_days):
        for rec in self:
            rec.action_expire_password()
            body = self.env['mail.render.mixin'].with_context(lang=rec.lang)._render_template(
                self.env.ref('zehntech_password_security.password_expire'),
                model='res.users', res_ids=rec.ids,
                engine='qweb_view', options={'post_process': True},
                add_context={'day_remain': delta_days},
            )[rec.id]
            subject = self.env['mail.render.mixin'].with_context(lang=rec.lang)._render_template(
                self.env.ref('zehntech_password_security.password_expire_subject'),
                model='res.users', res_ids=rec.ids,
                engine='qweb_view', options={'post_process': True},
            )[rec.id]

            msg_values = {
                'model': 'res.users',
                'res_id': rec.id,
                'body': escape(body),
                'is_internal': True,
                'message_type': 'email_outgoing',
                'subject': subject,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                'partner_ids': rec.partner_id.ids,
                'email_add_signature': True,
            }
            # Create the message and get the message_id
            message = self.env['mail.message'].create(msg_values)
            message_id = message.message_id  # Extract the message_id from the created message
            # Add the message_id to the msg_values
            msg_values['message_id'] = message_id
            new_message = self.env['mail.thread']._message_create([msg_values])
            self.env['mail.thread']._fallback_lang()._notify_thread(new_message, msg_values)
            
            if rec.notification_type == 'email':
                mail = self.env['mail.mail'].search([('message_id', '=', new_message.message_id)])
                if mail:
                    mail.send()

    def _compute_next_password_write_date(self):
        params = self.env["ir.config_parameter"].sudo()
        password_expiration = int(params.get_param('auth_password_policy.password_expiration'))
        
        for rec in self:
            if password_expiration > 0:
                rec.next_password_write_date = (rec.password_write_date + timedelta(days=password_expiration))
            else:
                rec.next_password_write_date = False

    @api.model
    def get_password_policy(self):
        data = super(ResUsers, self).get_password_policy()

        params = self.env['ir.config_parameter'].sudo()
        data.update(
            {
                'password_lower': int(params.get_param('auth_password_policy.password_lower', default=0)),
                'password_upper': int(params.get_param('auth_password_policy.password_upper', default=0)),
                'password_numeric': int(params.get_param('auth_password_policy.password_numeric', default=0)),
                'password_special': int(params.get_param('auth_password_policy.password_special', default=0)),
            }
        )

        return data

    def _check_password_policy(self, passwords):
        result = super(ResUsers, self)._check_password_policy(passwords)

        for password in passwords:
            if not password:
                continue
            self._check_password(password)

        return result

    def password_match_message(self):
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        password_lower = int(params.get_param('auth_password_policy.password_lower', default=0))
        password_upper = int(params.get_param('auth_password_policy.password_upper', default=0))
        password_numeric = int(params.get_param('auth_password_policy.password_numeric', default=0))
        password_special = int(params.get_param('auth_password_policy.password_special', default=0))
        message = []

        if password_lower > 0:
            message.append(_("\n* Lowercase letter (at least %s characters)") % str(password_lower))
        if password_upper > 0:
            message.append(_("\n* Uppercase letter (at least %s characters)") % str(password_upper))
        if password_numeric > 0:
            message.append(_("\n* Numeric digit (at least %s characters)") % str(password_numeric))
        if password_special > 0:
            message.append(_("\n* Special character (at least %s characters)") % str(password_special))
        if message:
            message = [_("Must contain the following:")] + message

        minlength = int(params.get_param("auth_password_policy.minlength", default=0))
        if minlength > 0:
            message = [_("Password must be %d characters or more.") % minlength] + message

        return "\r".join(message)

    def _check_password(self, password):
        self._check_password_rules(password)
        self._check_password_history(password)
        return True

    def _check_password_rules(self, password):
        self.ensure_one()
        
        if not password:
            return True

        params = self.env["ir.config_parameter"].sudo()
        password_lower = int(params.get_param("auth_password_policy.password_lower", default=0))
        password_upper = int(params.get_param("auth_password_policy.password_upper", default=0))
        password_numeric = int(params.get_param("auth_password_policy.password_numeric", default=0))
        password_special = int(params.get_param("auth_password_policy.password_special", default=0))
        minlength = int(params.get_param("auth_password_policy.minlength", default=0))

        errors = []
        messages = []

        # Check minimum length
        minlength_status = len(password) >= minlength
        messages.append(_("Password must be at least %d characters long: %s") % (minlength, "✅" if minlength_status else "❌"))
        if not minlength_status:
            errors.append(_("Password must be at least %d characters long.") % minlength)

        # Check lowercase letters
        lowercase_count = len(re.findall(r'[a-z]', password))
        lowercase_status = password_lower <= 0 or lowercase_count >= password_lower
        messages.append(_("Password must contain at least %d lowercase letter(s): %s (Found: %d)") % (password_lower, "✅" if lowercase_status else "❌", lowercase_count))
        if not lowercase_status:
            errors.append(_("Password must contain at least %d lowercase letter(s).") % password_lower)

        # Check uppercase letters
        uppercase_count = len(re.findall(r'[A-Z]', password))
        uppercase_status = password_upper <= 0 or uppercase_count >= password_upper
        messages.append(_("Password must contain at least %d uppercase letter(s): %s (Found: %d)") % (password_upper, "✅" if uppercase_status else "❌", uppercase_count))
        if not uppercase_status:
            errors.append(_("Password must contain at least %d uppercase letter(s).") % password_upper)

        # Check numeric digits
        numeric_count = len(re.findall(r'\d', password))
        numeric_status = password_numeric <= 0 or numeric_count >= password_numeric
        messages.append(_("Password must contain at least %d numeric digit(s): %s (Found: %d)") % (password_numeric, "✅" if numeric_status else "❌", numeric_count))
        if not numeric_status:
            errors.append(_("Password must contain at least %d numeric digit(s).") % password_numeric)

        # Check special characters
        special_count = len(re.findall(r'[\W_]', password))
        special_status = password_special <= 0 or special_count >= password_special
        messages.append(_("Password must contain at least %d special character(s): %s (Found: %d)") % (password_special, "✅" if special_status else "❌", special_count))
        if not special_status:
            errors.append(_("Password must contain at least %d special character(s).") % password_special)

        # If there are any errors, raise them all at once
        if errors:
            is_backend = True  # Default to backend
           
            # Check if request context is available
            if http.request:
                path_info = http.request.httprequest.path
                # Check if the request is for Portal or Signup (Frontend)
                is_frontend = any(route in path_info for route in [
                    "/web/signup",
                    "/web/reset_password",
                    "/my",
                    "/portal"
                ])
                # Check for backend routes
                is_backend = path_info.startswith('/web') and not is_frontend
            if is_backend:
                # Backend: Use plain text formatting (no HTML)
                error_message = _("Password does not meet the following requirements:\n\n")
                error_message += "\n".join(f"- {msg}" for msg in messages)

            else:
                # Frontend (Signup, Portal): Use HTML
                error_message = _("<strong>Password does not meet the following requirements:</strong><ul>")
                error_message += "".join(f"<li>{msg}</li>" for msg in messages)
                error_message += "</ul>"
                error_message = Markup(error_message)

            raise UserError(error_message)

        return True

    def _check_password_history(self, password):
        """It validates proposed password against existing history
        :raises: UserError on reused password
        """
        if not password:
            return True
        crypt = self._crypt_context()
        params = self.env["ir.config_parameter"].sudo()
        password_history = int(params.get_param("auth_password_policy.password_history", default=0))

        if not password_history:  # disabled
            recent_passes = self.env["res.users.pass.history"]
        elif password_history < 0:  # unlimited
            recent_passes = self.password_history_ids
        else:
            recent_passes = self.password_history_ids[:password_history]

        if recent_passes.filtered(lambda r: crypt.verify(password, r.password_crypt)):
            raise UserError(_("Cannot use the most recent %d passwords") % password_history)

        return True
    def _password_has_expired(self):
        self.ensure_one()
        if not self.password_write_date:
            return True

        params = self.env["ir.config_parameter"].sudo()
        password_expiration = int(params.get_param("auth_password_policy.password_expiration"))
        if password_expiration <= 0:
            return False
        
        test_password_expiration = params.get_param("auth_password_policy.test_password_expiration")

        if test_password_expiration:

            days = (fields.Datetime.now() - self.password_write_date).total_seconds() // 60

            return days > password_expiration

        else:

            return fields.Datetime.now() >= self.next_password_write_date
        
    def action_expire_password(self , signup_type="reset", expiration_hours=24):
        expiration_hours = 24  # 1 day expiration
        for user in self:
            partner = user.partner_id
            # Generate token with expiration
            token = partner._generate_signup_token(expiration=expiration_hours)
            # Store the signup type (this replaces signup_prepare)
            partner.write({
                "signup_type": signup_type,  # Use "reset" or another relevant type
            })
            # (OPTIONAL) Return the token if needed
            return token

    def _set_encrypted_password(self, uid, pw):
        """It saves password crypt history for history rules"""

        res = super(ResUsers, self)._set_encrypted_password(uid, pw)
        self.env["res.users.pass.history"].create({"user_id": uid, "password_crypt": pw})
        return res

    def action_reset_password(self):
        """Disallow password resets inside of Minimum Hours"""
        min_reset_interval_hours = int(self.env['ir.config_parameter'].sudo().get_param('minimum_reset_interval'))
        
        for user in self:
            if user.password_write_date:
                next_allowed_reset = user.password_write_date + timedelta(hours=min_reset_interval_hours)
                print(f"Checking password reset for user {user.id}. Next allowed reset time: {next_allowed_reset}")
                if fields.Datetime.now() < next_allowed_reset:
                    print(f"Password reset attempt too soon for user {user.id}.")
                    raise UserError(
                        _(
                           "You cannot reset your password until %s. "
                           "Please wait for %d hours."
                           
                        ) % (
                            next_allowed_reset.strftime('%d-%m-%Y'),
                            min_reset_interval_hours
                        )
                    )
        
        print("Password reset allowed. Proceeding with the reset process.")
        return super(ResUsers, self).action_reset_password()
