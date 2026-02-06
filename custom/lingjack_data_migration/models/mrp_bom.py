from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class MRPBoM(models.Model):
    _inherit = 'mrp.bom'

    empty_cabinet_bom = fields.Boolean(string='Empty Cabinet BOM', default=False)
    lingjack_product_category = fields.Char(string='Lingjack Product Category')

    # @api.model
    def api_create_empty_cabinet_bom(self):
        Bom = self.env['mrp.bom'].sudo()
        BomLine = self.env['mrp.bom.line'].sudo()

        # 1. Get ALL empty cabinet sub-BOMs
        sub_boms = Bom.search([('empty_cabinet_bom', '=', True)])
        if not sub_boms:
            return False

        for sub_bom in sub_boms:

            # 2. Find parent BOM lines that use THIS sub-BOM product
            parent_lines = BomLine.search([
                ('product_id', '=', sub_bom.product_id.id)
            ])

            for parent_line in parent_lines:
                parent_bom = parent_line.bom_id

                # Keep qty before unlink
                parent_qty = parent_line.product_qty

                # 3. Remove the sub-assembly line
                parent_line.unlink()

                # 4. Expand sub-BOM components into parent BOM
                for line in sub_bom.bom_line_ids:
                    BomLine.create({
                        'bom_id': parent_bom.id,
                        'product_id': line.product_id.id,
                        # Quantity scaled by parent usage
                        'product_qty': line.product_qty * parent_qty,
                        'product_uom_id': line.product_uom_id.id,
                        'sequence': line.sequence,
                    })
            sub_bom.unlink()

        return True
        
    @api.model
    def api_update_operation_to_bom(self , name=False, operation_list = []):
        Operation = self.env['mrp.routing.workcenter'].sudo()
        Bom = self.env['mrp.bom'].sudo()
        workcenter = self.env['mrp.workcenter'].sudo()
        if not name:
            return False
        
        boms = Bom.search([('lingjack_product_category', '=', name)])

        for bom in boms:
            for operation in operation_list:
                Operation.create({
                    'bom_id': bom.id,
                    'name': operation,
                    'workcenter_id': workcenter.sudo().search([('name', '=', operation)], limit=1).id or workcenter.sudo().create({'name': operation}).id,
                    'sequence': operation_list.index(operation) + 1,
                })
        return True

    # @api.model
    def api_update_serial_categories_in_bom(self):
        category = self.env['setsco.category'].sudo().search([])

        for cat in category:
            com_no_to_search = cat.description
            label = self.env['product.product'].sudo().search([('default_code', '=', com_no_to_search)], limit=1)
            label.sudo().write({
                'is_setsco_label': True,
            })
            if label:
                bom_to_update =self.env['mrp.bom.line'].sudo().search([('product_id', '=', label.id)]).mapped('bom_id')
                if bom_to_update:
                    for bom in bom_to_update:
                        bom.product_id.write({
                            'requires_setsco_serial': True,
                            'setsco_category_id': cat.id,
                        })


    def migration_button(self):
        self.api_update_serial_categories_in_bom()
        self.api_create_empty_cabinet_bom()
        