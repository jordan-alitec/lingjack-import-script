/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { MrpDisplayAction } from "@mrp_workorder/mrp_display/mrp_display_action";

// Patch MrpDisplayAction to add date_finished field for shop floor schedule display
patch(MrpDisplayAction.prototype, {
    // Override the fieldsStructure method to add date_finished field
    get fieldsStructure() {
        let res = super.fieldsStructure;
        
        // Add date_finished field to mrp.production
        if (!res['mrp.production'].includes('date_finished')) {
            res['mrp.production'].push('date_finished');
        }
        
        // Add date_finished field to mrp.workorder
        if (!res['mrp.workorder'].includes('date_finished')) {
            res['mrp.workorder'].push('date_finished');
            res['mrp.workorder'].push('is_last_station_for_production');
            res['mrp.workorder'].push('can_user_mark_done');
        }

        if (!res['mrp.workorder'].includes('production_id')) {
            res['mrp.workorder'].push('production_id');
        }
        
        // Also add date_deadline for production orders
        if (!res['mrp.production'].includes('date_deadline')) {
            res['mrp.production'].push('date_deadline');
        }
        
        // Add duration_expected for workorders
        if (!res['mrp.workorder'].includes('duration_expected')) {
            res['mrp.workorder'].push('duration_expected');
        }
        
        return res;
    }
}); 