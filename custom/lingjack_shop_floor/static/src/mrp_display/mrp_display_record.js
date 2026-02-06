/** @odoo-module **/

import { MrpDisplayRecord } from "@mrp_workorder/mrp_display/mrp_display_record";
import { patch } from "@web/core/utils/patch";
import { formatDateTime } from "@web/core/l10n/dates";

patch(MrpDisplayRecord.prototype, {
/***
   Lingjack Engineering don`t allow user operator to update and register production through shopfloor
   so during setup we just disable that
***/

    setup() {
        super.setup();
        this.displayRegisterProduction = false;
    },
     get displayDoneButton() {
        return false;
    },

    formatScheduleDate(dateStr) {
        if (!dateStr) {
            return '';
        }

        
        try {
            // Parse the date string
            const date = new Date(dateStr);
            
            // Check if date is valid
            if (isNaN(date.getTime())) {
                return dateStr;
            }
            
            // Format date as "MM/DD HH:MM" for compact display
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            
            return `${day}/${month} ${hours}:${minutes}`;
        } catch (error) {
            return dateStr;
        }
    },

    /**
     * Format duration for display in shop floor
     * @param {number} durationMinutes - Duration in minutes
     * @returns {string} - Formatted duration string
     */
    formatDuration(durationMinutes) {
        if (!durationMinutes || durationMinutes <= 0) {
            return '';
        }
        
        try {
            const totalMinutes = Math.round(durationMinutes);
            const hours = Math.floor(totalMinutes / 60);
            const minutes = totalMinutes % 60;
            
            if (hours > 0) {
                return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
            } else {
                return `${minutes}m`;
            }
        } catch (error) {
            return String(durationMinutes);
        }
    }
}); 