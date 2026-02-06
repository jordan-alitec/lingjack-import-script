/** @odoo-module **/

import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';

/**
 * Stock Barcode Model Patch
 * Prevents "Mandatory source location" popup when custom scanner is active
 */
export const stockBarcodeModelPatch = {
    dependencies: [],
    
    start(env) {
        // Global flag to track if custom scanner is active
        window.customScannerActive = false;
        
        return {};
    }
};

// Register the patch
registry.category("services").add("stock_barcode_model_patch", stockBarcodeModelPatch);
