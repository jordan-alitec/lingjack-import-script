/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodeMRPModel from "@stock_barcode_mrp/models/barcode_mrp_model";

patch(BarcodeMRPModel.prototype, {
    async _createState() {
        const state = await super._createState();
        
        // Check if we have SFP pickings available in context
        if (this.env.services.action && this.env.services.action.currentAction) {
            const context = this.env.services.action.currentAction.context || {};
            if (context.sfp_pickings_available && context.sfp_picking_ids) {
                state.sfpPickings = {
                    available: true,
                    ids: context.sfp_picking_ids,
                    count: context.sfp_picking_count,
                    showMessage: context.show_sfp_message
                };
            }
        }
        
        return state;
    },

    async actionOpenSfpPickings() {
        if (this.state.sfpPickings && this.state.sfpPickings.available) {
            const action = await this.orm.call(
                'mrp.production',
                'action_view_sfp_pickings',
                [this.resId],
                {}
            );
            if (action && action.type !== 'ir.actions.act_window_close') {
                this.env.services.action.doAction(action);
            }
        }
    }
});

