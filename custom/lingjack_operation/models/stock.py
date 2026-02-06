from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    purchase_requisition_id = fields.Many2one('purchase.requisition', string="Purchase Requisition")
    attention_ids = fields.Many2many('res.partner','stock_picking_attention_rel','picking_id','partner_id',string='Attention')

    remarks_do = fields.Char(string='Picking List Remarks')
    do_remarks = fields.Char(string='DO Remarks')


    approve = fields.Boolean(string='Approved', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)

    supplier_do_number = fields.Text(string='Supplier DO Number')
    previous_transfer = fields.Char(string='Previous Transfer')

    picking_id = fields.Many2one(
        'stock.picking',
        string="GRN Number",
        readonly=True
    )
    cs_in_charge_id = fields.Many2one(comodel_name='res.users', string='CS-In Charge')
    delivery_ref = fields.Char(string='Delivery Ref')


    driver_status = fields.Selection([
        ('unassign', 'Unassign'),
        ('picked', 'Picked'),
        ('in_progress', 'In Progress'),
        ('delivered_complete', 'Delivered (Complete)'),
        ('delivered_incomplete', 'Delivered (Incomplete)'),
    ], string='Driver Status', default='unassign', tracking=True)

    delivered_by = fields.Many2one('res.users', string='Delivered By', tracking=True)
    driver_picking_date = fields.Datetime(string='Driver Picking Date', tracking=True)
    remarks = fields.Text(string='Remarks')

    customer_signature = fields.Binary(string="Customer Signature")
    signature_name = fields.Char(string="Name")
    signature_date = fields.Datetime(string="Date")

    total_time_hhmmss = fields.Char(
        string='Total Time (HH:MM:SS)',
        compute='_compute_total_time_hhmmss',
        store=True
    )

    @api.onchange('picking_type_id', 'location_dest_id')
    def _onchange_pending_onsite_transfer(self):
        for picking in self:
            warning = picking._get_pending_onsite_transfer_warning()
            if warning:
                return warning

    def _get_pending_onsite_transfer_warning(self):
        self.ensure_one()

        if not (
                self.picking_type_id
                and self.location_dest_id
                and self.picking_type_id.is_on_site_transfer
                and self.picking_type_id.code == 'internal'
                and self.location_dest_id.usage == 'internal'
        ):
            return False

        domain = [
            ('id', '!=', self.id),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('location_dest_id', '=', self.location_dest_id.id),
            ('state', 'in', ('draft', 'confirmed', 'assigned')),
        ]

        picking = self.env['stock.picking'].search(domain, limit=1)

        if not picking:
            return False

        return {
            'warning': {
                'title': _('Warning'),
                'message': _(
                    'There’s a pending Delivery "%s" for "%s".\n'
                    'Please confirm if you want to create a new transfer to the same location.'
                ) % (picking.name, self.location_dest_id.display_name)
            }
        }

    @api.depends('driver_picking_date', 'signature_date')
    def _compute_total_time_hhmmss(self):
        for rec in self:
            if rec.driver_picking_date and rec.signature_date:

                diff = rec.signature_date - rec.driver_picking_date
                total_seconds = int(diff.total_seconds())

                if total_seconds < 0:
                    total_seconds = abs(total_seconds)

                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                rec.total_time_hhmmss = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                rec.total_time_hhmmss = "00:00:00"

    def action_picked(self):
        for rec in self:
            rec.sudo().write({
                'driver_status': 'picked',
                'delivered_by': self.env.user.id,
                'driver_picking_date': fields.Datetime.now(),
            })

    def action_signature_update(self):
        self.ensure_one()
        return {
            'name': 'Update Signature Details',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.signature.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
                'default_customer_signature': self.customer_signature,
                'default_signature_name': self.signature_name,
                'default_signature_date': self.signature_date,
            }
        }

    def action_open_attachment_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Attachments',
            'res_model': 'stock.picking.attachment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
            },
        }

    @api.onchange('customer_signature')
    def _onchange_customer_signature(self):
        if self.customer_signature:
            self.signature_date = datetime.now()

    def action_delivered_incomplete(self):
        self.ensure_one()
        return {
            'name': 'Delivered (Incomplete)',
            'type': 'ir.actions.act_window',
            'res_model': 'driver.incomplete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
            }
        }


    def _get_next_transfers(self):
        result = super()._get_next_transfers()
        result.write({'purchase_requisition_id': self.purchase_requisition_id.id})
        result.write({'supplier_do_number': self.supplier_do_number,'previous_transfer': self.name})
        result.write({'picking_id': self.id})

        for old_move, new_move in zip(self.move_ids_without_package, result.move_ids_without_package):
            if old_move.description_picking:
                new_move.write({'description_picking': old_move.description_picking})
        return result

    def action_approve(self):
        for picking in self:
            picking.write({
                'approve': True,
                'approved_by': self.env.user.id,
                'approved_on': datetime.now()
            })

    def button_validate(self):
        for move in self.move_ids_without_package:
            demand_qty = move.product_uom_qty
            done_qty = move.quantity
            # So that this will not affect pick component from stock report which assume demand qty as 0
            if done_qty > demand_qty and demand_qty != 0:
                raise ValidationError(
                    _("Delivery quantity of '%s' %.2f exceeds demand quantity %.2f. Please adjust the quantity.")
                    % (move.product_id.display_name, done_qty, demand_qty)
                )
        return super().button_validate()

    def ac_button_validate(self):
        # This will escalate the driver priviledge to super to validate the DO
        # Other access rights will limit their ability to edit
        super().sudo().button_validate()

    @api.model_create_multi
    def create(self, vals):
        picking = super(StockPicking, self).create(vals)

        if picking.origin:
            purchase_order = self.env['purchase.order'].search([
                ('name', '=', picking.origin)
            ], limit=1)
            if purchase_order and purchase_order.requisition_id:
                picking.purchase_requisition_id = purchase_order.requisition_id.id

        return picking

    def copy(self, default=None):
        default = dict(default or {})

        default.update({
            'driver_status': 'unassign',
            'delivered_by': False,
            'driver_picking_date': False,
            'remarks': False,

            'customer_signature': False,
            'signature_name': False,
            'signature_date': False,
            'total_time_hhmmss': "00:00:00",
        })

        return super(StockPicking, self).copy(default)

class StockMove(models.Model):
    _inherit = 'stock.move'

    purchase_requisition_id = fields.Many2one('purchase.requisition', string="Purchase Requisition")
    
    @api.onchange('product_id')
    def _onchange_product_id_description(self):
        if self.product_id:
            self.description_picking = self.product_id.name
        else:
            self.description_picking = False

    @api.constrains('quantity')
    def _onchange_quantity_done_kit_sync(self):
        for move in self:

            # Need to return this cause will affect manufacturing order
            if not move.picking_id:
                continue

            # find phantom BOM
            bom = move.bom_line_id.bom_id
            if not bom or bom.type != 'phantom':
                continue

            # find BOM line for this product
            line = bom.bom_line_ids.filtered(lambda l: l.product_id == move.product_id)
            if not line or line.product_qty <= 0:
                continue

            # check if entered quantity is multiple of BOM quantity
            if move.quantity % line.product_qty != 0:
                move.quantity = 0
                raise UserError(
                    f"Quantity of {move.product_id.display_name} must be a multiple of "
                    f"{line.product_qty} (BOM requirement)."
                )

            # number of kits being delivered
            kits = move.quantity / line.product_qty

            # sync sibling components in the same picking
            sibling_moves = move.picking_id.move_ids_without_package.filtered(
                lambda m: m.product_id.id in bom.bom_line_ids.mapped('product_id').ids
                           and m.id != move.id
            )

            for sibling in sibling_moves:
                sibling_line = bom.bom_line_ids.filtered(lambda l: l.product_id == sibling.product_id)
                sibling.quantity = sibling_line.product_qty * kits

    def _get_new_picking_values(self):
        vals = super(StockMove, self)._get_new_picking_values()
        order = self.sale_line_id.order_id if self.sale_line_id else False
        vals.update({
            'cs_in_charge_id': order.cs_in_charge_id.id if order else False,
            'attention_ids': [(6, 0, order.ship_to_attention_ids.ids)] if order else [],
        })
        return vals

    def _prepare_account_move_line(
            self, qty, cost, credit_account_id, debit_account_id, svl_id, description):
        lines = super()._prepare_account_move_line(
            qty, cost, credit_account_id, debit_account_id, svl_id, description)
        if self.scrap_id:
            analytic_id = self.scrap_id.analytic_account_id.id
            if analytic_id:
                distribution = {analytic_id: 100.0}
                for i, line in enumerate(lines):
                    if isinstance(line, tuple) and isinstance(line[2], dict):
                        lines[i][2]['analytic_distribution'] = distribution
        return lines

    @api.onchange('quantity', 'product_uom_qty')
    def _onchange_quantity_check_demand(self):
        for move in self:
            if (
                move.product_uom_qty
                and move.quantity
                and move.quantity > move.product_uom_qty):
                raise ValidationError(_("Delivery quantity of '%s' (%.2f) exceeds demand quantity (%.2f).\n"
                        "Please adjust the quantity.") %(move.product_id.display_name,move.quantity,move.product_uom_qty,))


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom,location_dest_id, name, origin, company_id, values):
        move_vals = super()._get_stock_move_values(product_id, product_qty, product_uom,location_dest_id, name, origin, company_id, values)

        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            phantom_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', sale_line.product_id.product_tmpl_id.id),('type', '=', 'phantom')])

            if phantom_bom:
                move_vals['description_picking'] = product_id.name
            else:
                move_vals['description_picking'] = sale_line.name
        return move_vals


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    analytic_account_id = fields.Many2one('account.analytic.account',string='Analytic Account')


class StockReturnPickingLine(models.TransientModel):
    _inherit = 'stock.return.picking.line'

    @api.constrains('quantity')
    def _check_quantity_not_exceed_move(self):
        for record in self:
            if record.quantity > record.move_id.product_qty:
                raise ValidationError(
                    "Return quantity cannot exceed the original move quantity. "
                    f"Maximum allowed: {record.move_id.product_qty}"
                )


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _get_check_values(self, quality_point):
        vals = super(StockMoveLine, self)._get_check_values(quality_point)
        vals.update({'description': self.move_id.move_orig_ids.description_picking})
        return vals

class StockLandedCostInherit(models.Model):
    _inherit = 'stock.landed.cost'

    mrp_production_ids = fields.Many2many(groups=False)

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_on_site_transfer = fields.Boolean(string="On-Site Transfer")
