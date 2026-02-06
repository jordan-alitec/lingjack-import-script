/** @odoo-module **/
//Imports
import { patch } from "@web/core/utils/patch";
import { MrpDisplay } from "@mrp_workorder/mrp_display/mrp_display";

//MrpDisplay Extended
patch(MrpDisplay.prototype, {
	// Overrides the relevantRecords method to sort records by urgency field
    get relevantRecords() {
		let res = super.relevantRecords;
        const urgencyOrder = {
            'urgent': 3,
            'high': 2,
            'normal': 1,
            'low_priority': 0,
        };
        res.sort((u1, u2) => {
            const uA = urgencyOrder[u1.data.urgency];
            const uB = urgencyOrder[u2.data.urgency];
            return uB - uA;
        });
        return res;
    },
});
