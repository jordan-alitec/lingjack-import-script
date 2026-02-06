from odoo import models, fields

class UserPasswordLog(models.Model):
    _name = "user.password.log"
    _description = "User Password Change Log"
    _order = "change_date desc"

    user_id = fields.Many2one('res.users', string="User", required=True, help="The user whose password was changed.")
    changed_by = fields.Many2one('res.users', string="Changed By", required=True, default=lambda self: self.env.user, help="The user who changed the password.")
    old_password_hash = fields.Char(string="Old Password (Hashed)", readonly=True,help="The previous password hash, stored securely for reference.")
    new_password_hash = fields.Char(string="New Password (Hashed)", readonly=True, help="The new password hash, stored securely after the change.")
    change_date = fields.Datetime(string="Change Date", default=fields.Datetime.now,  help="The date and time when the password change occurred.")