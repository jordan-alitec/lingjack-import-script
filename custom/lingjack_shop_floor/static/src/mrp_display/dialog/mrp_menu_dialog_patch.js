/** @odoo-module **/

import { MrpMenuDialog } from '@mrp_workorder/mrp_display/dialog/mrp_menu_dialog';
import { patch } from '@web/core/utils/patch';
import { _t } from '@web/core/l10n/translation';

patch(MrpMenuDialog.prototype, {
    async markMoDone() {
        console.log('ghi');
        await this.props.reload(this.props.record);
        return

        const productionId = this.props.record.data.production_id[0];
        const ctx = { active_workorder_id: this.props.record.resId };
        const action = await this.orm.call('mrp.production', 'action_lj_mark_mo_done', [[productionId]], { context: ctx });
        console.log(action);
        if (action) {
            await this.action.doAction(action, {
                onClose: async () => {
                    await this.props.reload(this.props.record);
                },
            });
        } else {
            await this.props.reload(this.props.record);
        }

    },
});


