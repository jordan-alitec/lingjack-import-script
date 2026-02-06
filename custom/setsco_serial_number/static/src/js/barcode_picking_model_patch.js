/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import BarcodeModel from '@stock_barcode/models/barcode_model';

/**
 * Patch BarcodePickingModel to prevent "Mandatory source location" popup
 * when custom scanner is active
 */
patch(BarcodePickingModel.prototype, {
    
    _processBarcode(barcode) {
        // If custom scanner is active, skip the mandatory source location check
        // console.log(window.customScannerActive);
        if (window.customScannerActive) {
           
            return true;
            // return { title: "Custom scanner active", error: false };
        }
        
        // Call original method if custom scanner is not active
        return super._processBarcode(...arguments);
    }
});

/**
 * Patch BarcodeModel to prevent "This product doesn't exist" notification
 * when custom scanner is active
 */
patch(BarcodeModel.prototype, {
    
    noProductToast(barcodeData) {
        // If custom scanner is active, skip the "product doesn't exist" notification
        if (!window.customScannerActive) {
            return Promise.resolve();
        }
        
        // Call original method if custom scanner is not active
        return super.noProductToast(...arguments);
    }
});
