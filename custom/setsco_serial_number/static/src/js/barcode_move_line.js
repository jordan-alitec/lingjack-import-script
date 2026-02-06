/** @odoo-module **/

import LineComponent from '@stock_barcode/components/line';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";


patch(LineComponent.prototype, {

    setup() {
        super.setup();
        this.action = useService("action");
    },

    onClickAssignSetsconumber(ev) {
        this.action.doAction({
            name: "Select Setsco Serial Range",
            type: "ir.actions.act_window",
            res_model: "setsco.serial.selection.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_move_id: this.line.move_id,
                default_move_line_id: this.line.id,
                default_product_id: this.line.product_id.id,
                default_quantity: 0,
//                default_quantity: this.line.qty_done,
            },
        });
    }

});
