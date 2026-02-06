/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import MainComponent from "@stock_barcode/components/main";

patch(MainComponent.prototype, {
    openMap() {
        const pickingId = this.env.model.resId;

        this.env.services.action.doAction("lj_barcode_qty_demand.action_stock_location_selection", {
            additionalContext: {
                default_picking_id: pickingId,
            }
        });
    },
});
