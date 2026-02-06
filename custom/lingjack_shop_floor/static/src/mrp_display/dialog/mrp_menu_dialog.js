/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { MrpMenuDialog } from "@mrp_workorder/mrp_display/dialog/mrp_menu_dialog";

// Patch MrpMenuDialog to handle the action_pick_component action
patch(MrpMenuDialog.prototype, {
    // Override callAction to handle our custom action

    async callAction(method, props = {}) {
        if (method === 'action_pick_component') {
            // Call the server-side action_pick_component method
            const action = await this.orm.call(
                 this.props.record.resModel,
                'action_pick_component',
                [this.props.record.resId],
                {
                    context: { from_shop_floor: true }
                }
            );
            
            if (action && typeof action === 'object') {
                this.action.doAction(action, {
                    onClose: async () => {
                        await this.props.reload(this.props.record);
                    },
                    props,
                });
                this.props.close();
            } else {
            }


            
        } else {
            // Call the original method for other actions
            return super.callAction(method, props);
        }
    },

    async markMoDone() {
       
            const productionId = this.props.record.data.production_id[0];
            const ctx = { active_workorder_id: this.props.record.resId };
            const action = await this.orm.call('mrp.production', 'action_lj_mark_mo_done', [[productionId]], { context: ctx });
            // Try catch so that it wont throw error
            try {
                if (action) {
                    await this.action.doAction(action, {
                        onClose: async () => {
                            await this.props.close();
                        },
                    });
                } else {
                    await this.props.close();
                }
            } catch (error) {
                await this.props.close();
            }
            

    },
}); 