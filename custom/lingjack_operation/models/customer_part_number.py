from odoo import models, fields

class CustomerPartNumber(models.Model):
    _name = 'customer.part.number'
    _description = 'Customer Part Number'

    name = fields.Char()
    replace_with_customer_description = fields.Boolean(string="Replace with Customer Description")
    part_line_ids = fields.One2many('customer.part.line', 'customer_part_id', string='Customer Parts')

class CustomerPartLine(models.Model):
    _name = 'customer.part.line'
    _description = 'Customer Part Line'

    customer_part_id = fields.Many2one('customer.part.number', string='Customer Part')
    product_id = fields.Many2one('product.product', string='Product')
    customer_part_number = fields.Char(string='Customer Part Number')
    customer_description = fields.Text(string='Customer Description')