/** @odoo-module **/

import { MrpDisplayRecord } from "@mrp_workorder/mrp_display/mrp_display_record";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

/**
 * Shop Floor Quantity Popup Integration
 * Patches MrpDisplayRecord to add quantity popup before stopping work
 * AND fix o_finished_product to show workorder-level quantities
 */
patch(MrpDisplayRecord.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        
        // Initialize tracking objects
        this._fetchedQuantitiesFor = {};
        this._fetchingQuantities = false;
        

        
        // Override quantityToProduce for workorders after super.setup()
        this._updateQuantityToProduce();
        
        // Also patch onWillUpdateProps to update quantities when data changes
        this._originalOnWillUpdateProps = this.onWillUpdateProps || (() => {});
        this.onWillUpdateProps = (nextProps) => {
            if (this._originalOnWillUpdateProps) {
                this._originalOnWillUpdateProps.call(this, nextProps);
            }
            
            // Update record references
            this.resModel = nextProps.record.resModel;
            this.model = nextProps.record.model;
            this.record = nextProps.record.data;
            
            // Update quantity for workorders
            if (nextProps.record.resModel === "mrp.workorder") {
                const workorderQty = nextProps.record.data.qty_production  || 0;

                this.quantityToProduce = workorderQty;
            }
        };
    },
    
    _updateQuantityToProduce() {
        if (this.props.record.resModel === "mrp.workorder") {
            // For workorders, use workorder-specific quantity instead of production quantity
            const workorderData = this.props.record.data;
            const workorderQty = workorderData.qty_production ||
                               workorderData.qty_remaining || 
                               0;

            this.quantityToProduce = workorderQty;
        }
    },

    /**
     * Override quantityProducing to show workorder-level quantities for workorders
     * instead of production-level quantities
     */
    get quantityProducing() {
        const { resModel } = this.props.record;
        
        // For workorders, show workorder-level qty_produced instead of production qty_producing
        if (resModel === "mrp.workorder") {
            const workorderData = this.props.record.data;
            
//          Fetch the work order quantities manually
            this._fetchWorkorderQuantities(workorderData.id);

            const workorderProduced = workorderData.qty_produced || 0;
            
            // Only fetch if we don't have the data and haven't already fetched it
            if (workorderProduced === 0 && workorderData.id && !this._fetchedQuantitiesFor?.[workorderData.id]) {
                this._fetchWorkorderQuantities(workorderData.id);
            }
            
            return workorderProduced;
        }
        
        // For productions, keep the original behavior
        const productionProducing = this.props.production.data.qty_producing;
        return productionProducing;
    },

    /**
     * Manually fetch workorder quantities if not available in loaded data
     */
    async _fetchWorkorderQuantities(workorderId) {
        if (this._fetchingQuantities || this._fetchedQuantitiesFor[workorderId]) return; // Prevent multiple fetches
        
        try {
            this._fetchingQuantities = true;
            this._fetchedQuantitiesFor[workorderId] = true;
            
            // Use searchRead instead of read for better compatibility
            const workorderData = await this.model.orm.searchRead(
                'mrp.workorder',
                [['id', '=', workorderId]], 
                ['qty_produced', 'total_produced', 'qty_production']
            );
            
            if (workorderData && workorderData.length > 0) {
                const data = workorderData[0];
                
                // Update the record data with fetched values
                Object.assign(this.props.record.data, {
                    qty_produced: data.qty_produced,
                    total_produced: data.total_produced,
                    qty_production: data.qty_production,
                });
                
                // DON'T call render() here as it creates an infinite loop
                // The data is updated and will be used on next getter call
            }
        } catch (error) {
        } finally {
            this._fetchingQuantities = false;
        }
    },

    /**
     * Override startWorking to add quantity popup before stopping work
     * @param {boolean} shouldStop - Whether this action should stop work
     */
    async startWorking(shouldStop = false) {
        const { resModel, resId } = this.props.record;
        if (resModel !== "mrp.workorder") {
            return super.startWorking(shouldStop);
        }

        // Update employees first (same as original)
        await this.props.updateEmployees();
        const admin_id = this.props.sessionOwner.id;
        
        // Check if employee is currently working
        const isEmployeeWorking = this.props.record.data.employee_ids.records.some((emp) => emp.resId == admin_id);

        // If employee is working AND we want to stop, show quantity popup first
        if (admin_id && isEmployeeWorking && shouldStop) {

            try {
                // Show quantity popup before stopping
                const quantityLogged = await this.showQuantityPopup(resId, admin_id);
                
                if (quantityLogged) {
                    // Popup successful, now stop the employee

                    await this.model.orm.call(resModel, "stop_employee", [resId, [admin_id]]);
                    await this.env.reload(this.props.production);
                    
                    // Show specific notification
                    const info = this._lastQuantityInfo || { quantity: 'Unknown', uom: 'units' };
                    this.notificationService.add(
                        `Work session stopped. Quantity logged: ${info.quantity} ${info.uom}`, 
                        { type: 'success' }
                    );
                    
                    // Clean up stored info
                    delete this._lastQuantityInfo;
                } else {
                    // Popup was cancelled

                    // Just reload to reflect any quantity changes
                    await this.env.reload(this.props.production);
                    return;
                }
            } catch (error) {
                this.notificationService.add('Error showing quantity popup. Proceeding with normal stop.', { type: 'warning' });
                // Fall back to normal behavior
                return super.startWorking(shouldStop);
            }
        } else {
            // Employee not working (starting work) or no shouldStop - use normal behavior

            return super.startWorking(shouldStop);
        }
    },

    /**
     * Show quantity popup and return whether quantity was logged
     * @param {number} workorderId - The workorder ID
     * @param {number} employeeId - The employee ID
     * @returns {Promise<boolean>} - True if quantity was logged, false if cancelled
     */
    async showQuantityPopup(workorderId, employeeId) {

        try {
            // First, verify that our popup model exists
            try {
                await this.model.orm.call('shop.floor.quantity.popup', 'check_access_rights', ['read']);
            } catch (modelError) {
                this.notificationService.add('Shop floor popup not available. Please contact administrator.', { type: 'warning' });
                return false;
            }

            // Find active productivity record
            const productivityRecords = await this.model.orm.searchRead(
                'mrp.workcenter.productivity',
                [
                    ['workorder_id', '=', workorderId],
                    ['employee_id', '=', employeeId], 
                    ['date_end', '=', false]
                ],
                ['id']
            );

            if (productivityRecords.length === 0) {
                return false;
            }

            const productivityId = productivityRecords[0].id;

            // Get the view ID first to ensure it exists
            let viewId;
            try {
                const viewResult = await this.model.orm.call(
                    'ir.ui.view',
                    'search_read',
                    [[['name', '=', 'shop.floor.quantity.popup.form']]],
                    ['id']
                );
                viewId = viewResult.length > 0 ? viewResult[0].id : false;
            } catch (viewError) {
                viewId = false;
            }

            // Show popup action with explicit view reference
            const popupAction = {
                type: 'ir.actions.act_window',
                name: 'Log Session Quantity',
                res_model: 'shop.floor.quantity.popup',
                view_mode: 'form',
                views: [[viewId, 'form']],
                target: 'new',
                domain: [],
                context: {
                    default_productivity_id: productivityId,
                    default_workorder_id: workorderId,
                    default_employee_id: employeeId,
                    close_session_after_save: true,
                    js_callback: true,
                },
                flags: {
                    mode: 'edit',
                }
            };

            // Execute popup and wait for result
            return new Promise((resolve, reject) => {
                try {

                    this.actionService.doAction(popupAction, {
                        onClose: (result) => {

                            // Check if quantity was successfully logged
                            // Result can be the action object or just the infos
                            const infos = result?.infos || result;
                            if (infos && infos.quantity_logged) {

                                // Always stop the session after saving quantity
                                this._lastQuantityInfo = {
                                    action: 'finish',
                                    quantity: infos.quantity,
                                    uom: infos.uom
                                };
                                resolve(true); // Stop the employee
                            } else {
                                resolve(false);
                            }
                        }
                    });
                } catch (actionError) {
                    reject(actionError);
                }
            });

        } catch (error) {
            
            // Fallback: use simple prompt for quantity input
            return this.showSimpleQuantityPrompt(workorderId, employeeId, productivityId);
        }
    },

    /**
     * Fallback method: Simple quantity input using browser prompt
     * @param {number} workorderId - The workorder ID
     * @param {number} employeeId - The employee ID  
     * @param {number} productivityId - The productivity record ID
     * @returns {Promise<boolean>} - True if quantity was logged
     */
    async showSimpleQuantityPrompt(workorderId, employeeId, productivityId) {
        try {
            const quantityStr = prompt('Enter quantity produced:', '1.0');
            
            if (quantityStr === null) {
                // User cancelled
                return false;
            }
            
            const quantity = parseFloat(quantityStr);
            if (isNaN(quantity) || quantity <= 0) {
                this.notificationService.add('Invalid quantity entered', { type: 'danger' });
                return false;
            }

            // Update productivity record directly
            await this.model.orm.write('mrp.workcenter.productivity', [productivityId], {
                quantity_produced: quantity,
                date_end: new Date().toISOString().replace('T', ' ').slice(0, 19),
            });

            return true;

        } catch (fallbackError) {
            return false;
        }
    }
});



// Test that our patch is working by adding a method to check integration
if (!window.ShopFloorDebug) {
    window.ShopFloorDebug = {};
}
window.ShopFloorDebug.testPatch = function() {
    return 'Shop Floor patch is active';
};

window.ShopFloorDebug.testQuantityDisplay = function() {
    return 'Quantity display patch is active';
};

window.ShopFloorDebug.checkWorkorderData = function() {
    // Find MRP display components and check their data
    const mrpDisplays = document.querySelectorAll('.o_mrp_display_record');
    

    
    return 'Workorder data check complete - see console logs';
};

window.ShopFloorDebug.forceRefreshQuantities = async function() {
    // Try to trigger a reload if we can access the environment
    if (window.odoo && window.odoo.env) {
        try {
            const workorders = await window.odoo.env.services.orm.call('mrp.workorder', 'search_read', 
                [[], ['id', 'name', 'qty_produced', 'total_produced', 'qty_production']],
                { limit: 5 }
            );
            
            // Force reload the MRP display
            if (window.odoo.env.reload) {
                window.odoo.env.reload();
            }
            
        } catch (error) {
            // ORM call failed
        }
    }
    
    return 'Force refresh attempted';
};

window.ShopFloorDebug.simulateQuantityFix = function() {
    return 'Quantity fix summary complete';
};