/** @odoo-module */

import { useSubEnv } from "@odoo/owl";
import { FSMProductCatalogKanbanRecord } from "@industry_fsm_sale/components/product_catalog/kanban_record";
import { rpc } from "@web/core/network/rpc";
import { useService } from '@web/core/utils/hooks';

export class LingjackServiceProductCatalogKanbanRecord extends FSMProductCatalogKanbanRecord {
    setup() {
        super.setup();
        this.orm = useService('orm');
        useSubEnv({
            ...this.env,
            fsm_task_id: this.props.record.context.fsm_task_id,
            resetQuantity: this.debouncedUpdateQuantity.bind(this),
        });
    }

    async _updateQuantity() {
        // Get special_id from context
        const special_id = this.props.record.context.special_id;
        const { action, price, min_quantity } = await rpc("/product/catalog/update_order_line_info", {
            order_id: this.env.orderId,
            product_id: this.env.productId,
            quantity: this.productCatalogData.quantity,
            res_model: this.env.orderResModel,
            task_id: this.env.fsm_task_id,
            special_id: special_id,
        });
        if (price) {
            this.productCatalogData.price = parseFloat(price);
        }
        if (min_quantity) {
            this.productCatalogData.minimumQuantityOnProduct = min_quantity;
        } else {
            this.productCatalogData.minimumQuantityOnProduct = 0;
        }
        if (action && action !== true) {
            const actionContext = {
                'default_product_id': this.props.record.data.id,
            };
            const options = {
                additionalContext: actionContext,
                onClose: async (closeInfo) => {
                    await this._refreshQuantity(special_id);
                },
            };
            await this.action.doAction(action, options);
        } else {
            // No action wizard - refresh quantity immediately after update
            await this._refreshQuantity(special_id);
        }
    }

    async _refreshQuantity(special_id) {
        // Refresh quantity from sale order lines
        // If special_id is provided, calculate from bus_quantities JSON
        const lines = await this.orm.searchRead(
            'sale.order.line',
            [
                ["task_id", "=", this.env.fsm_task_id],
                ["product_id", "=", this.env.productId],
                ["product_uom_qty", ">", 0],
            ],
            ['product_uom_qty', 'bus_quantities']
        );
        
        if (special_id) {
            // Calculate quantity from bus_quantities for the specified bus(es)
            const bus_names = special_id.split(',').map(b => b.trim());
            let total_qty = 0;
            for (const line of lines) {
                const bus_qty_dict = line.bus_quantities || {};
                for (const bus_name of bus_names) {
                    if (bus_name in bus_qty_dict) {
                        total_qty += bus_qty_dict[bus_name];
                    }
                }
            }
            this.productCatalogData.quantity = total_qty;
          
        } else {
            // No special_id - use total line quantity
            this.productCatalogData.quantity = lines.reduce((total, line) => total + line.product_uom_qty, 0);
        }
    }
}

