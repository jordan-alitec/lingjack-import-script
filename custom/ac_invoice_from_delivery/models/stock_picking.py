from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    def _get_action(self, action_xmlid):
        result = super(PickingType, self)._get_action(action_xmlid)
        if self.code == 'outgoing':
            result['context'].update({'tree_view_ref':'ac_invoice_from_delivery.vpicktree_inherit_add_field_invoice_state'})
        return result


class StockPicking(models.Model):
    _inherit = "stock.picking"

    invoice_state = fields.Selection([('invoiced', 'Invoiced'), ('2binvoiced', 'To Be Invoiced')],
                                     compute='_compute_invoice_status', search='_search_invoice_state',
                                     string="Invoice Control", copy=False)
    invoice_id = fields.Many2one('account.move', copy=False)
    service_order_ids = fields.Many2many('repair.order', string='Service Orders')

    def _compute_invoice_status(self):
        self.invoice_state = '2binvoiced'
        invoiced_pick_id = self.filtered(lambda r: r.invoice_id and r.invoice_id.state != 'cancel')
        invoiced_pick_id.invoice_state = 'invoiced'

    def _search_invoice_state(self, operator, value):
        if operator == '=' and value == '2binvoiced':
            pick_id = self.env['stock.picking'].search(['|', ('invoice_id', '=', False), ('invoice_id.state', '=', 'cancel')])
            domain = [('id', 'in', pick_id.ids)]
        else:
            domain = [(1, '=', 1)]
        return domain

    def action_create_invoice(self):
        pickings = self.filtered(
            lambda p: p.picking_type_code == "outgoing" and p.sale_id and not p.invoice_id
        )
        if not pickings:
            raise UserError(_("No eligible delivery orders found."))
        if pickings.filtered(lambda p: p.state not in ("done", "assigned")):
            raise UserError(_("All delivery orders must be done or ready."))
        if len(pickings.mapped("sale_id.partner_id")) != 1:
            raise UserError(_("All delivery orders must belong to the same customer."))

        seq, lines = 10, []
        for picking in pickings.sorted("name"):
            picking_seen = set()
            scheduled_date = ''
            if picking.scheduled_date:
                scheduled_date = picking.scheduled_date.strftime('%d/%m/%y')
            lines.append((0, 0, {
                "display_type": "line_section",
                "name": _("Delivery Order: %s ( %s ) Sale Order: %s") % (picking.name, scheduled_date, picking.sale_id.name),
                "sequence": seq,
            }))
            seq += 1

            moves = picking.move_ids.filtered(lambda m: m.product_uom_qty > 0).sorted(key=lambda m: m.sequence)
            for move in moves:
                sale_line = move.sale_line_id
                if not sale_line:
                    continue

                key = (picking.id, sale_line.id)
                if key in picking_seen:
                    continue

                for vals in move._prepare_invoice_line():
                    if vals.get("display_type") in ("line_section", "line_note"):
                        continue
                    if move.bom_line_id and move.bom_line_id.product_qty:
                        vals["quantity"] = move.quantity / move.bom_line_id.product_qty

                    vals["name"] = move.description_picking

                    vals["sequence"] = seq
                    lines.append((0, 0, vals))
                    seq += 1

                picking_seen.add(key)

        sale = pickings.mapped("sale_id")[0]
        move_lines = pickings.mapped("move_ids").filtered(lambda m: m.product_uom_qty > 0)
        ref_data = move_lines._get_sale_ref()
        
        #Call the fucnction to prepare the invoice line for downpayment and service
        for sale_order in pickings.mapped("sale_id"):
            downpayment_service_lines = self._prepare_invoice_line_for_downpayment_service(sale_id=sale_order, sequence=seq)
            
        lines += downpayment_service_lines

        vals = sale._prepare_invoice()
        vals.update({
            "ref": ref_data.get("ref"),
            "invoice_origin": ref_data.get("invoice_origin"),
            "invoice_line_ids": lines,
        })

        invoice = self.env["account.move"].create(vals)
        pickings.write({"invoice_id": invoice.id})
        return invoice

    def _prepare_invoice_line_for_downpayment_service(self, sale_id=False, sequence=0):
        res = []
        down_payment_section_added = False
        invoiceable_lines = sale_id._get_invoiceable_lines(final=True)
        for line in invoiceable_lines:
            if not down_payment_section_added and line.is_downpayment:
                res.append((0,0,(
                    sale_id._prepare_down_payment_section_line(
                        sequence=sequence,
                    )
                )))
                down_payment_section_added = True
                sequence += 1
            if line.is_downpayment:
                res.append((0,0,(
                    line._prepare_invoice_line(
                        sequence=sequence,
                    )
                )))
                sequence += 1
            if line.product_type == 'service':# and line.product_id.default_code == 'DISCOUNT':
                res.append((0,0,(
                    line._prepare_invoice_line(
                        sequence=sequence,
                    )
                )))
                sequence += 1
        return res

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _invoice_section_name(self):
        """
        This method is used to get the section name for an invoice line.
        It returns either the name of the delivery order associated with the invoice
        or a string indicating that there are associated service orders.

        :return: A string indicating the section name for the invoice line.
        :rtype: str
        """
        self.ensure_one()
        section_name = self.picking_id and self.picking_id.name or False
        origin = self.origin
        picking = self.picking_id

        if self.picking_id and self.picking_id.service_order_ids:
            return f"Service Order: {','.join(self.picking_id.service_order_ids.mapped('name'))}"
        else:
            delivery_ref = picking.delivery_ref if picking and picking.delivery_ref else ''
            if delivery_ref:
                section_name = f"{section_name} ({delivery_ref})"

            if origin:
                return f"Delivery Order: {section_name} / Sale Order: {origin}"
            else:
                return f"Delivery Order: {section_name}"


    def _prepare_invoice_line(self):
        sorted_move_id = self.sorted(key=lambda r: r.picking_id.id)
        sequence, do_check, res = 10, False, []
        sorted_move_id = sorted_move_id.filtered(lambda x:x.quantity)
        for rec in sorted_move_id:
            # Add a section name for the delivery order
            do_name = rec._invoice_section_name()
            if do_check != do_name:
                section_vals = {
                    'sequence': sequence,
                    'display_type': 'line_section',
                    'name': do_name,
                }
                sequence += 1
                res.append(section_vals)
                do_check = do_name

            # Add the invoice line
            sale_line_id = rec.sale_line_id
            if not sale_line_id:
                continue
            vals = sale_line_id._prepare_invoice_line()
            sale_uom_id = sale_line_id.product_uom
            sale_uom_quantity = rec.product_uom._compute_quantity(rec.quantity, sale_uom_id)
            # vals['sequence'] = sequence
            vals['quantity'] = sale_uom_quantity
            res.append(vals)
            sequence += 1

        # down_payment_section_added = False
        # invoiceable_lines = self.picking_id.sale_id._get_invoiceable_lines(final=True)
        # for line in invoiceable_lines:
        #     if not down_payment_section_added and line.is_downpayment:
        #         res.append(
        #             self.picking_id.sale_id._prepare_down_payment_section_line(
        #                 sequence=sequence,
        #             )
        #         )
        #         down_payment_section_added = True
        #         sequence += 10
        #     if line.is_downpayment:
        #         res.append(
        #             line._prepare_invoice_line(
        #                 sequence=sequence,
        #             )
        #         )
        #         sequence += 10
        #     if line.product_type == 'service':# and line.product_id.default_code == 'DISCOUNT':
        #         res.append(
        #             line._prepare_invoice_line(
        #                 # sequence=sequence,
        #             )
        #         )
        #         sequence += 10

            # if line.product_type == 'service' and line.product_id.name == 'Delivery Charge':
            #     res.append(
            #         line._prepare_invoice_line(
            #             sequence=sequence,
            #         )
            #     )
            #     sequence += 10

            # if line.product_type == 'service' and line.product_id.name == 'Discount':
            #     res.append(
            #         line._prepare_invoice_line(
            #             sequence=sequence,
            #         )
            #     )
            #     sequence += 10
            #
            # if line.product_type == 'service' and line.product_id.name == 'Price Difference ':
            #     res.append(
            #         line._prepare_invoice_line(
            #             sequence=sequence,
            #         )
            #     )
            #     sequence += 10

        return res

    def _get_sale_ref(self):
        sale_line_id = self.mapped('sale_line_id')
        order_id = sale_line_id.mapped('order_id')
        customer_ref_all = list(set(order_id.mapped('client_order_ref')))
        customer_ref_lst = [i for i in customer_ref_all if i]
        # customer_ref_lst = list(set(order_id.mapped('client_order_ref')))
        so_lst = list(set(order_id.mapped('name')))
        res = {
            'ref': len(customer_ref_lst) > 0 and ', '.join(customer_ref_lst) or False,
            'invoice_origin': len(so_lst) > 0 and ', '.join(so_lst) or False
        }
        return res

