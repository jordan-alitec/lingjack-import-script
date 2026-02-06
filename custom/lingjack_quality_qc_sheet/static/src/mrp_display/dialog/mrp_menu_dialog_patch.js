/** @odoo-module **/

import { MrpMenuDialog } from '@mrp_workorder/mrp_display/dialog/mrp_menu_dialog';
import { MrpDisplayAction } from '@mrp_workorder/mrp_display/mrp_display_action';
import { patch } from '@web/core/utils/patch';
import { _t } from '@web/core/l10n/translation';

// Patch MrpDisplayAction to include qc_spreadsheet_id field
patch(MrpDisplayAction.prototype, {
    get fieldsStructure() {
        const res = super.fieldsStructure;
        
        // Add qc_spreadsheet_id field to mrp.production if not already present
        if (!res['mrp.production'].includes('qc_spreadsheet_id')) {
            res['mrp.production'].push('qc_spreadsheet_id');
        }
        
        return res;
    }
});

patch(MrpMenuDialog.prototype, {
    async openQcSpreadsheet() {
        try {
            const productionId = this.props.record.data.production_id[0];
            const action = await this.orm.call('mrp.production', 'action_open_qc_spreadsheet', [[productionId]]);
            
            if (action) {
                await this.action.doAction(action, {
                    onClose: async () => {
                        // Optionally reload the workorder data if needed
                        await this.props.reload(this.props.record);
                    },
                });
            } else {
                // Show notification if no QC sheet is available
                this.notification.add(
                    _t('No QC Sheet available for this Manufacturing Order'),
                    { type: 'warning' }
                );
            }
        } catch (error) {
            this.notification.add(
                _t('Error opening QC Sheet: %s', error.message || error),
                { type: 'danger' }
            );
        }
    },
});
