from odoo import models, fields, api

class StockLocationSelection(models.Model):
    _name = 'stock.location.selection'
    _description = 'Stock Location Selection'

    picking_id = fields.Many2one("stock.picking", string="Picking")
    location_dest_id = fields.Many2one('stock.location', 'Destination Location')
    location_id = fields.Many2one("stock.location", string="Source Location")
    is_manually_update_location = fields.Boolean(string="Is Manually Location Update")
    location_selection = fields.Selection([('location', 'Location'), ('destination_location', 'Destination Location')], default='location',string="Location")

    def button_confirm(self):
        picking = self.picking_id
        if not picking or picking.state == "done":
            return

        vals = {
            k: v.id for k, v in {
                "location_id": self.location_id,
                "location_dest_id": self.location_dest_id,
            }.items() if v
        }

        if vals and self.is_manually_update_location:
            picking.write(vals)
            picking.move_line_ids.write(vals)

    def action_open_location_scanner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'name': 'Scan Location',
            'tag': 'lj_barcode_qty_demand.location_scanner',
            'context': {'wizard_id': self.id},
            'params': {
                'wizard_id': self.id,
                'purpose': 'location',
                'picking_id': self.picking_id.id if self.picking_id else False,
                'location_selected': self.location_selection
            },
            'target': 'new',
        }