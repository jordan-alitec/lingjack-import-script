from odoo import models, fields

class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    remarks = fields.Text(string="Remarks")
    supplier_warranty = fields.Float(string="Supplier Warranty Period (Days)",digits=(10, 0))
