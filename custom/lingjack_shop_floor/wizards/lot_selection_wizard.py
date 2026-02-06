# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class LotSelectionWizard(models.TransientModel):
    """Wizard for manual lot selection when required"""
    _name = 'lot.selection.wizard'
    _description = 'Lot Selection Wizard'

    production_id = fields.Many2one(
        'mrp.production',
        string='Production Order',
        required=True,
        readonly=True
    )

    component_line_ids = fields.One2many(
        'lot.selection.wizard.line',
        'wizard_id',
        string='Components Requiring Lot Selection'
    )

   

    def action_confirm_lot_selection(self):
        """Confirm lot selection and proceed with production"""
        self.ensure_one()
        
        # Check if all moves have lots assigned
        moves_without_lots = []
        for line in self.component_line_ids:
            if not line.move_id.lot_ids:
                moves_without_lots.append(line.product_id.display_name)
        
        if moves_without_lots:
            raise ValidationError(
                _('Please select lots for the following components:\n%s') % 
                '\n'.join(moves_without_lots)
            )
        

        self.production_id.button_mark_done()
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Lot Selection Complete'),
        #         'message': _('Lot selection completed successfully. You can now proceed with production.'),
        #         'type': 'success',
        #         'sticky': False,
        #     }
        # }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to populate component lines"""
        wizards = super().create(vals_list)
        
        for wizard in wizards:
            if wizard.production_id:
                # Find components that require manual lot selection
                component_lines = []
                for move in wizard.production_id.move_raw_ids:
                    if (move.product_id.tracking in ['lot', 'serial'] and 
                        move.product_id.manual_lot_reservation and
                        not move.lot_ids):
                        
                        component_lines.append((0, 0, {
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_qty': move.product_uom_qty,
                            'uom_id': move.product_uom.id,
                        }))
                
                wizard.component_line_ids = component_lines
        
        return wizards

    @api.model
    def default_get(self, fields_list):
        """Set default values for the wizard"""
        res = super().default_get(fields_list)
        
        production_id = self.env.context.get('default_production_id')
        if production_id:
            production = self.env['mrp.production'].browse(production_id)
            res['production_id'] = production_id
        
        return res


class LotSelectionWizardLine(models.TransientModel):
    """Line for lot selection wizard"""
    _name = 'lot.selection.wizard.line'
    _description = 'Lot Selection Wizard Line'

    wizard_id = fields.Many2one(
        'lot.selection.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True
    )

    product_qty = fields.Float(
        string='Quantity Required',
        readonly=True
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='UOM',
        readonly=True
    )

    selected_lots_display = fields.Char(
        string='Selected Lots',
        compute='_compute_selected_lots_display',
        store=False,
        help='Display of currently selected lots'
    )

    def action_view_stock_move(self):
        """Open the stock move to allow proper lot selection"""
        self.ensure_one()
        
        if not self.move_id:
            raise UserError(_('No stock move found for this component.'))
        
        # Pass the wizard ID in context so we can return to it
        return self.move_id.with_context(
            lot_selection_wizard_id=self.wizard_id.id
        ).action_open_lot_selection()

    @api.depends('move_id', 'move_id.lot_ids')
    def _compute_selected_lots_display(self):
        """Compute display of selected lots"""
        for line in self:
            if line.move_id and line.move_id.lot_ids:
                lot_names = ', '.join(line.move_id.lot_ids.mapped('name'))
                line.selected_lots_display = lot_names
            else:
                line.selected_lots_display = 'No lots selected'

    @api.depends('move_id', 'move_id.lot_ids')
    def _compute_lot_status(self):
        """Compute lot selection status"""
        for line in self:
            if not line.move_id:
                line.lot_status = 'not_selected'
            elif not line.move_id.lot_ids:
                line.lot_status = 'not_selected'
            elif len(line.move_id.lot_ids) == 1:
                line.lot_status = 'selected'
            else:
                line.lot_status = 'partial'
