from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    temp_company_id = fields.Char(string='Temp Company ID')


    @api.model
    def match_employee_to_company(self, dict={}):
        '''
        dict is a dictionary of the following format:
        dict = {
            'LJE': 2,
        }
        '''
        HREmployee = self.env['hr.employee'].sudo()
        # 1. Get ALL employees
        employee = HREmployee.search([])
        for employee in employee:
            try:
                company_id = dict[employee.temp_company_id]
                if company_id:
                    employee.write({
                        'company_id': company_id
                    })
                else:
                    continue
            except KeyError:
                continue
        return True
         

class HRDepartment(models.Model):
    _inherit = 'hr.department'

    temp_company_id = fields.Char(string='Temp Company ID')

    @api.model
    def match_department_to_company(self, dict={}):
        '''
        dict is a dictionary of the following format:
        dict = {
            'LJE': 2,
        }
        '''
        HRDepartment = self.env['hr.department'].sudo()
        department = HRDepartment.search([])
        for department in department:
            try:
                company_id = dict[department.temp_company_id]
                if company_id:
                    department.write({
                        'company_id': company_id
                    })
                else:
                    continue
            except KeyError:
                continue
        return True