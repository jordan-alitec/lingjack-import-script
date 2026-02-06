from odoo import models, fields, api


class ControlTag(models.Model):
    _name = 'control.tag' 
    _description = 'Control Tag'

    '''
        This model is used to generate distribution records for the control tag.
        it will pull from stock.move.line when validate
    '''

    #Field than required for generating distribution records
    invoice_id = fields.Many2one(comodel_name='account.move', string='Invoice', ondelete='cascade')
    move_line_id = fields.Many2one(comodel_name='stock.move.line', string='Move Line')

    serial_id = fields.Many2one(comodel_name='stock.lot', string='Serial Number', related='move_line_id.lot_id', store=True, readonly=False)

    # Data migration might not available the invoice id i will wneed to have related field but stored so that we can input

    invoice_number = fields.Char(string='Invoice Number', related='invoice_id.name', store=True, readonly=False)
    customer_name = fields.Char(string='Company Name', related='invoice_id.partner_id.name', store=True, readonly=False)
    invoice_date = fields.Date(string='Invoice Date', related='invoice_id.date', store=True, readonly=False)
    customer_reference = fields.Char(string='Customer Reference', related='invoice_id.ref', store=True, readonly=False)
    #TODO: future if inherit with project.project should get from there instead of a project field
    project = fields.Char(string='Project', related='invoice_id.project', store=True, readonly=False)
    item_code = fields.Char(string='Item Code', related='move_line_id.product_id.default_code', store=True, readonly=False)
    name = fields.Char(string='Control Tag Name', related='serial_id.name', store=True, readonly=False)
    quantity = fields.Float(string='Quantity', related='move_line_id.quantity', store=True, readonly=False)
    key_by = fields.Char(string='Key By', related='invoice_id.create_uid.name', store=True, readonly=False)
    salesperson = fields.Char(string='Salesperson', related='invoice_id.invoice_user_id.name', store=True, readonly=False)
    purchase_order = fields.Char(string='PO #', compute='get_purchase_order', store=True, readonly=False)

    @api.depends('serial_id')
    def get_purchase_order(self):
        for record in self:
            if record.serial_id.purchase_order_ids:
                purchase_orders = record.serial_id.purchase_order_ids.mapped('name')
                record.purchase_order = (', ').join(purchase_orders)
            else:
                record.purchase_order = ''

