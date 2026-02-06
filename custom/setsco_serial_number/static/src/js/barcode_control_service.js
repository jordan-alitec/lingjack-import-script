/** @odoo-module **/

import { registry } from '@web/core/registry';

/**
 * Barcode Control Service
 * Manages global barcode service state to prevent conflicts with custom scanners
 */
export const barcodeControlService = {
    dependencies: [],
    
    start() {
        return {
            // Global flag to disable barcode processing
            isDisabled: false,
            
            // Disable global barcode service
            disable() {
                this.isDisabled = true;
                
            },
            
            // Enable global barcode service
            enable() {
                this.isDisabled = false;
                console.log('Global barcode service enabled');
            },
            
            // Check if barcode service is disabled
            isBarcodeDisabled() {
                return this.isDisabled;
            }
        };
    }
};

// Register the service
registry.category("services").add("barcode_control", barcodeControlService);
