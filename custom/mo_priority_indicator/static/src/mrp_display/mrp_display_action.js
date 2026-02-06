/** @odoo-module */
//Imports
import { patch } from "@web/core/utils/patch";
import { MrpDisplayAction } from "@mrp_workorder/mrp_display/mrp_display_action";

//MrpDisplayAction Extended
patch(MrpDisplayAction.prototype, {
	// Overrides the fieldsStructure method to add urgency field in mrp.production and mrp.workorder models
    get fieldsStructure() {
        let res = super.fieldsStructure;
        res['mrp.production'].push('urgency');
		res['mrp.workorder'].push('urgency');
        return res;
    }
})
