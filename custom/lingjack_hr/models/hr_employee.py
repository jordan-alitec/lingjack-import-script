from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression

from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging
_logger = logging.getLogger(__name__)


class SGHREmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _lang_get(self):
        return self.env['res.lang'].get_installed()

    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.", groups="base.group_user,hr.group_hr_user", copy=False)
    birthday = fields.Date('Date of Birth', groups="base.group_user,hr.group_hr_user", tracking=True)
    certificate = fields.Selection([('graduate', 'Graduate'), ('bachelor', 'Bachelor'), ('master', 'Master'), ('doctor', 'Doctor'), ('other', 'Other'),], 'Certificate Level', groups="base.group_user,hr.group_hr_user", tracking=True)
    children = fields.Integer(string='Number of Dependent Children', groups="base.group_user,hr.group_hr_user", tracking=True)
    country_of_birth = fields.Many2one('res.country', string="Country of Birth", groups="base.group_user,hr.group_hr_user", tracking=True)
    distance_home_work = fields.Integer(string="Home-Work Distance", groups="base.group_user,hr.group_hr_user", tracking=True)
    distance_home_work_unit = fields.Selection([('kilometers', 'km'), ('miles', 'mi'),], 'Home-Work Distance unit', tracking=True, groups="base.group_user,hr.group_hr_user", default='kilometers', required=True)
    emergency_contact = fields.Char("Contact Name", groups="base.group_user,hr.group_hr_user", tracking=True)
    emergency_phone = fields.Char("Contact Phone", groups="base.group_user,hr.group_hr_user", tracking=True)
    bank_account_id = fields.Many2one('res.partner.bank', 'Bank Account', domain="[('partner_id', '=', work_contact_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]", groups="base.group_user,hr.group_hr_user", tracking=True, help='Employee bank account to pay salaries')
    country_id = fields.Many2one('res.country', 'Nationality (Country)', groups="base.group_user,hr.group_hr_user", tracking=True)
    employee_type = fields.Selection([('employee', 'Employee'), ('worker', 'Worker'), ('student', 'Student'), ('trainee', 'Trainee'), ('contractor', 'Contractor'), ('freelance', 'Freelancer'),], string='Employee Type', default='employee', required=True, groups="base.group_user,hr.group_hr_user", help="Categorize your Employees by type. This field also has an impact on contracts. Only Employees, Students and Trainee will have contract history.")
    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), ('other', 'Other')], groups="base.group_user,hr.group_hr_user", tracking=True)

    identification_id = fields.Char(string='Identification No', groups="base.group_user,hr.group_hr_user", tracking=True)
    marital = fields.Selection(selection='_get_marital_status_selection', string='Marital Status', groups="base.group_user,hr.group_hr_user", default='single', required=True, tracking=True)
    passport_id = fields.Char('Passport No', groups="base.group_user,hr.group_hr_user", tracking=True)
    permit_no = fields.Char('Work Permit No', groups="base.group_user,hr.group_hr_user", tracking=True)
    pin = fields.Char(string="PIN", groups="base.group_user,hr.group_hr_user", copy=False, help="PIN used to Check In/Out in the Kiosk Mode of the Attendance application (if enabled in Configuration) and to change the cashier in the Point of Sale application.")
    place_of_birth = fields.Char('Place of Birth', groups="base.group_user,hr.group_hr_user", tracking=True)

    private_street = fields.Char(string="Private Street", groups="base.group_user,hr.group_hr_user")
    private_street2 = fields.Char(string="Private Street2", groups="base.group_user,hr.group_hr_user")
    private_city = fields.Char(string="Private City", groups="base.group_user,hr.group_hr_user")
    private_state_id = fields.Many2one("res.country.state", string="Private State", domain="[('country_id', '=?', private_country_id)]", groups="base.group_user,hr.group_hr_user")
    private_zip = fields.Char(string="Private Zip", groups="base.group_user,hr.group_hr_user")
    private_country_id = fields.Many2one("res.country", string="Private Country", groups="base.group_user,hr.group_hr_user")
    private_phone = fields.Char(string="Private Phone", groups="base.group_user,hr.group_hr_user")
    private_email = fields.Char(string="Private Email", groups="base.group_user,hr.group_hr_user")
    lang = fields.Selection(selection=_lang_get, string="Lang", groups="base.group_user,hr.group_hr_user")

    spouse_complete_name = fields.Char(string="Spouse Complete Name", groups="base.group_user,hr.group_hr_user", tracking=True)
    spouse_birthdate = fields.Date(string="Spouse Birthdate", groups="base.group_user,hr.group_hr_user", tracking=True)
    ssnid = fields.Char('SSN No', help='Social Security Number', groups="base.group_user,hr.group_hr_user", tracking=True)
    study_field = fields.Char("Field of Study", groups="base.group_user,hr.group_hr_user", tracking=True)
    study_school = fields.Char("School", groups="base.group_user,hr.group_hr_user", tracking=True)
    visa_no = fields.Char('Visa No', groups="base.group_user,hr.group_hr_user", tracking=True)
    visa_expire = fields.Date('Visa Expiration Date', groups="base.group_user,hr.group_hr_user", tracking=True)

    hours_last_month_display = fields.Char(compute='_compute_hours_last_month', groups="base.group_user,hr.group_hr_user")
    attendance_manager_id = fields.Many2one('res.users', store=True, readonly=False, domain="[('share', '=', False), ('company_ids', 'in', company_id)]", groups="base.group_user,hr_attendance.group_hr_attendance_manager", help="The user set in Attendance will access the attendance of the employee through the dedicated app and will be able to edit them.")


class SGHREmployeePublic(models.AbstractModel):
    _inherit = 'hr.employee.public'

    attendance_manager_id = fields.Many2one(related='employee_id.attendance_manager_id', groups="base.group_user,hr_attendance.group_hr_attendance_officer")


class SGHREmployeeBase(models.AbstractModel):
    _inherit = 'hr.employee.base'

    @api.model
    def _lang_get(self):
        return self.env['res.lang'].get_installed()

    def _get_marital_status_selection(self):
        return [
            ('single', _('Single')),
            ('married', _('Married')),
            ('cohabitant', _('Legal Cohabitant')),
            ('widower', _('Widower')),
            ('divorced', _('Divorced')),
        ]

    private_street = fields.Char(string="Private Street", groups="base.group_user,hr.group_hr_user")
    private_street2 = fields.Char(string="Private Street2", groups="base.group_user,hr.group_hr_user")
    private_city = fields.Char(string="Private City", groups="base.group_user,hr.group_hr_user")
    private_state_id = fields.Many2one("res.country.state", string="Private State", domain="[('country_id', '=?', private_country_id)]", groups="base.group_user,hr.group_hr_user")
    private_zip = fields.Char(string="Private Zip", groups="base.group_user,hr.group_hr_user")
    private_country_id = fields.Many2one("res.country", string="Private Country", groups="base.group_user,hr.group_hr_user")
    private_phone = fields.Char(string="Private Phone", groups="base.group_user,hr.group_hr_user")
    private_email = fields.Char(string="Private Email", groups="base.group_user,hr.group_hr_user")
    lang = fields.Selection(selection=_lang_get, string="Lang", groups="base.group_user,hr.group_hr_user")

    spouse_complete_name = fields.Char(string="Spouse Complete Name", groups="base.group_user,hr.group_hr_user", tracking=True)
    spouse_birthdate = fields.Date(string="Spouse Birthdate", groups="base.group_user,hr.group_hr_user", tracking=True)
    ssnid = fields.Char('SSN No', help='Social Security Number', groups="base.group_user,hr.group_hr_user", tracking=True)
    study_field = fields.Char("Field of Study", groups="base.group_user,hr.group_hr_user", tracking=True)
    study_school = fields.Char("School", groups="base.group_user,hr.group_hr_user", tracking=True)
    visa_no = fields.Char('Visa No', groups="base.group_user,hr.group_hr_user", tracking=True)
    visa_expire = fields.Date('Visa Expiration Date', groups="base.group_user,hr.group_hr_user", tracking=True)

    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), ('other', 'Other')], groups="base.group_user,hr.group_hr_user", tracking=True)
    marital = fields.Selection(selection='_get_marital_status_selection', string='Marital Status', groups="base.group_user,hr.group_hr_user", default='single', required=True, tracking=True)
    birthday = fields.Date('Date of Birth', groups="base.group_user,hr.group_hr_user", tracking=True)
    children = fields.Integer(string='Number of Dependent Children', groups="base.group_user,hr.group_hr_user", tracking=True)
    country_of_birth = fields.Many2one('res.country', string="Country of Birth", groups="base.group_user,hr.group_hr_user", tracking=True)
    place_of_birth = fields.Char('Place of Birth', groups="base.group_user,hr.group_hr_user", tracking=True)

    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.", groups="base.group_user,hr.group_hr_user", copy=False)
    pin = fields.Char(string="PIN", groups="base.group_user,hr.group_hr_user", copy=False, help="PIN used to Check In/Out in the Kiosk Mode of the Attendance application (if enabled in Configuration) and to change the cashier in the Point of Sale application.")
    certificate = fields.Selection([('graduate', 'Graduate'), ('bachelor', 'Bachelor'), ('master', 'Master'), ('doctor', 'Doctor'), ('other', 'Other'), ], 'Certificate Level', groups="base.group_user,hr.group_hr_user", tracking=True)
    bank_account_id = fields.Many2one('res.partner.bank', 'Bank Account', domain="[('partner_id', '=', work_contact_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]", groups="base.group_user,hr.group_hr_user", tracking=True, help='Employee bank account to pay salaries')
    country_id = fields.Many2one('res.country', 'Nationality (Country)', groups="base.group_user,hr.group_hr_user", tracking=True)
    employee_type = fields.Selection([('employee', 'Employee'), ('worker', 'Worker'), ('student', 'Student'), ('trainee', 'Trainee'), ('contractor', 'Contractor'), ('freelance', 'Freelancer'), ], string='Employee Type', default='employee', required=True, groups="base.group_user,hr.group_hr_user", help="Categorize your Employees by type. This field also has an impact on contracts. Only Employees, Students and Trainee will have contract history.")

    identification_id = fields.Char(string='Identification No', groups="base.group_user,hr.group_hr_user", tracking=True)
    passport_id = fields.Char('Passport No', groups="base.group_user,hr.group_hr_user", tracking=True)
    permit_no = fields.Char('Work Permit No', groups="base.group_user,hr.group_hr_user", tracking=True)
    emergency_contact = fields.Char("Contact Name", groups="base.group_user,hr.group_hr_user", tracking=True)
    emergency_phone = fields.Char("Contact Phone", groups="base.group_user,hr.group_hr_user", tracking=True)
    distance_home_work = fields.Integer(string="Home-Work Distance", groups="base.group_user,hr.group_hr_user", tracking=True)
    distance_home_work_unit = fields.Selection([('kilometers', 'km'), ('miles', 'mi'), ], 'Home-Work Distance unit', tracking=True, groups="base.group_user,hr.group_hr_user", default='kilometers', required=True)

    attendance_manager_id = fields.Many2one('res.users', store=True, readonly=False, domain="[('share', '=', False), ('company_ids', 'in', company_id)]", groups="base.group_user,hr_attendance.group_hr_attendance_manager", help="The user set in Attendance will access the attendance of the employee through the dedicated app and will be able to edit them.")
