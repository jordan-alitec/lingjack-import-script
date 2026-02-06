/** @odoo-module */

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { FSMProductCatalogKanbanModel } from "@industry_fsm_sale/components/product_catalog/kanban_model";

export class LingjackServiceProductCatalogKanbanModel extends FSMProductCatalogKanbanModel {
    async _loadData(params) {
        // Call grandparent's _loadData to avoid parent's RPC call, then make our own with special_id
        const result = await RelationalModel.prototype._loadData.call(this, ...arguments);
        
        if (!params.isMonoRecord && !params.groupBy.length) {
            // Override to add special_id parameter to the RPC call.
            const saleOrderLinesInfo = await rpc("/product/catalog/order_lines_info", {
                order_id: params.context.order_id,
                product_ids: result.records.map((rec) => rec.id),
                task_id: params.context.fsm_task_id,
                res_model: params.context.product_catalog_order_model,
                special_id: params.context.special_id,
            });
            // Valid props for ProductCatalogOrderLine component and its extensions
            // Base props: quantity, price, productType, readOnly, warning, productId
            // Sale-specific: deliveredQty (for ProductCatalogSaleOrderLine)
            // FSM Stock-specific: tracking, minimumQuantityOnProduct (patched by industry_fsm_stock)
            const validProps = ['quantity', 'price', 'productType', 'readOnly', 'warning', 'productId', 'deliveredQty', 'tracking', 'minimumQuantityOnProduct'];
            
            for (const record of result.records) {
                const data = saleOrderLinesInfo[record.id] || {};
                // Filter to only include valid props to avoid passing unknown props to component
                const filteredData = Object.keys(data)
                    .filter(key => validProps.includes(key))
                    .reduce((obj, key) => {
                        obj[key] = data[key];
                        return obj;
                    }, {});
                
                // Ensure required props have default values if missing
                // tracking and minimumQuantityOnProduct are required by ProductCatalogSaleOrderLine (patched by industry_fsm_stock)
                if (!('tracking' in filteredData)) {
                    filteredData.tracking = false;
                }
                if (!('minimumQuantityOnProduct' in filteredData)) {
                    filteredData.minimumQuantityOnProduct = 0;
                }
                // Ensure readOnly is explicitly set (default to false if missing)
                // This prevents issues where readOnly might be undefined and treated as truthy
                if (!('readOnly' in filteredData)) {
                    filteredData.readOnly = false;
                } else {
                    // Ensure it's a boolean, not a string or other type
                    filteredData.readOnly = Boolean(filteredData.readOnly);
                }
                
                record.productCatalogData = filteredData;
            }
        }
        return result;
    }
}

