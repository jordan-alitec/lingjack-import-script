/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ViewButton } from "@web/views/view_button/view_button";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ScannerDialog } from "./scanner_dialog";

/**
 * Helper function to check if js_class="list_scanner" is set
 */
function hasScanQRButtonClass(archInfo, env) {
    // Check env.config.viewSubType for standalone list views
    if (env.config.viewSubType === 'list_scanner') {
        return true;
    }
    // Check archInfo.xmlDoc for nested list views (one2many fields)
    if (archInfo && archInfo.xmlDoc) {
        const jsClass = archInfo.xmlDoc.getAttribute('js_class');
        return jsClass === 'list_scanner';
    }
    return false;
}

// Patch ListController
patch(ListController.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.notification = useService("notification");
    },

    /**
     * Check if Scan QR button should be displayed
     */
    get hasScanQRButton() {
        return hasScanQRButtonClass(this.archInfo, this.env);
    },

    /**
     * Handle Scan QR button click
     */
    async onClickScanQR() {
        await this._openScannerDialog();
    },

    /**
     * Open scanner dialog and handle scan result
     */
    async _openScannerDialog() {
        try {
            const devices = await window.__Html5QrcodeLibrary__.Html5Qrcode.getCameras();
            const supportedCodes = [
                { id: 1, label: 'code_128_reader', value: 'Code 128' },
                { id: 2, label: 'ean_reader', value: 'EAN' },
                { id: 3, label: 'ean_8_reader', value: 'EAN-8' },
                { id: 4, label: 'code_39_reader', value: 'Code 39' },
                { id: 5, label: 'code_39_vin_reader', value: 'Code 39 VIN' },
                { id: 6, label: 'codabar_reader', value: 'Codabar' },
                { id: 7, label: 'upc_reader', value: 'UPC' },
                { id: 8, label: 'upc_e_reader', value: 'UPC-E' },
                { id: 9, label: 'i2of5_reader', value: 'Interleaved 2 of 5' },
                { id: 10, label: '2of5_reader', value: 'Standard 2 of 5' },
                { id: 11, label: 'code_93_reader', value: 'Code 93' },
                { id: 12, label: 'ean_extended_reader', value: 'EAN Extended' },
            ];

            const facingMode = "environment";
            const qrCodeScanner = '';
            const codeType = 0;
            const deviceUid = devices[0]?.id || '';
            const barcodeReader = supportedCodes[0].label;

            this.dialogService.add(ScannerDialog, {
                facingMode,
                devices,
                supportedCodes,
                codeType,
                deviceUid,
                barcodeReader,
                qrCodeScanner,
                onResult: (result) => this._handleScanResult(result),
                onError: (error) => {
                    console.log("QR code not detected", error);
                    this.notification.add(_t("QR code not detected"), { type: 'warning' });
                },
            });
        } catch (err) {
            this.notification.add(_t("Camera Not Found: ") + err, { type: 'warning' });
        }
    },

    /**
     * Handle scan result - search, duplicate and link record
     */
    async _handleScanResult(barcodeValue) {
        try {
            // Get model name and parent_id from context
            const modelName = this.model.root.resModel;
            const context = this.props.context || {};
            console.log('context', context);
            const parentId = context.active_id;
            console.log('parentId', context);
            if (!parentId) {
                this.notification.add(_t("Parent ID not found in context"), { type: 'warning' });
                return;
            }

            // Call backend method to search, duplicate and link
            const result = await rpc("/web/dataset/call_kw", {
                model: 'lingjack.list.scanner.base',
                method: 'scan_and_duplicate_record',
                args: [modelName, barcodeValue, parentId],
                kwargs: {},
            });

            if (result.status === 'success') {
                this.notification.add(result.message || _t("Record duplicated successfully"), { 
                    type: 'success' 
                });
                // Reload the list to show the new record
                // For standalone list views, reload the model
                await this.model.load();
                this.render();
            } else if (result.status === 'not_found') {
                this.notification.add(result.message || _t("No record found"), { 
                    type: 'warning' 
                });
            } else {
                this.notification.add(result.message || _t("Error processing scan"), { 
                    type: 'danger' 
                });
            }
        } catch (error) {
            console.error("Error handling scan result:", error);
            this.notification.add(_t("Error processing scan: ") + error, { type: 'danger' });
        }
    },
});

// Patch ListRenderer for editable lists (one2many fields)
patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.notification = useService("notification");
        // Add Scan QR button to creates array if js_class="list_scanner" is set
        // This runs after super.setup() which sets this.creates
        if (hasScanQRButtonClass(this.props.archInfo, this.env)) {
            const originalCreates = this.creates || [];
            this.creates = [
                ...originalCreates,
                {
                    type: 'button',
                    string: 'Scan QR',
                    className: 'ml16',
                    icon: 'fa-qrcode',
                    tag: 'a',
                    clickParams: {
                        special: 'save',
                        onClick: () => this.onClickScanQR(),
                    },
                },
            ];
        }
    },

    /**
     * Check if Scan QR button should be displayed
     */
    get hasScanQRButton() {
        return hasScanQRButtonClass(this.props.archInfo, this.env);
    },

    /**
     * Handle Scan QR button click in renderer
     */
    async onClickScanQR() {
        await this._openScannerDialog();
    },

    /**
     * Open scanner dialog and handle scan result
     */
    async _openScannerDialog() {
        try {
            const devices = await window.__Html5QrcodeLibrary__.Html5Qrcode.getCameras();
            const supportedCodes = [
                { id: 1, label: 'code_128_reader', value: 'Code 128' },
                { id: 2, label: 'ean_reader', value: 'EAN' },
                { id: 3, label: 'ean_8_reader', value: 'EAN-8' },
                { id: 4, label: 'code_39_reader', value: 'Code 39' },
                { id: 5, label: 'code_39_vin_reader', value: 'Code 39 VIN' },
                { id: 6, label: 'codabar_reader', value: 'Codabar' },
                { id: 7, label: 'upc_reader', value: 'UPC' },
                { id: 8, label: 'upc_e_reader', value: 'UPC-E' },
                { id: 9, label: 'i2of5_reader', value: 'Interleaved 2 of 5' },
                { id: 10, label: '2of5_reader', value: 'Standard 2 of 5' },
                { id: 11, label: 'code_93_reader', value: 'Code 93' },
                { id: 12, label: 'ean_extended_reader', value: 'EAN Extended' },
            ];

            const facingMode = "environment";
            const qrCodeScanner = '';
            const codeType = 0;
            const deviceUid = devices[0]?.id || '';
            const barcodeReader = supportedCodes[0].label;

            this.dialogService.add(ScannerDialog, {
                facingMode,
                devices,
                supportedCodes,
                codeType,
                deviceUid,
                barcodeReader,
                qrCodeScanner,
                onResult: (result) => this._handleScanResult(result),
                onError: (error) => {
                    console.log("QR code not detected", error);
                    this.notification.add(_t("QR code not detected"), { type: 'warning' });
                },
            });
        } catch (err) {
            this.notification.add(_t("Camera Not Found: ") + err, { type: 'warning' });
        }
    },

    /**
     * Handle scan result - search, duplicate and link record
     */
    async _handleScanResult(barcodeValue) {
        try {
            // Get model name and parent_id from context
            const modelName = this.props.list.resModel;
            
            // Get parent_id from the form record context (for one2many fields)
            const formRecord = this.props.list.model?.root?.parent;
            const context = formRecord?.evalContext || this.props.list.context || {};
            
            const parentId = context.active_id;
            const list_context_str = this.props.archInfo.xmlDoc.getAttribute('context');
            let list_context = JSON.parse(list_context_str.replace(/'/g, '"'));
            const parent_field = list_context.parent_field;
            
            console.log('parent_field', parent_field);
            console.log('list_context', list_context);
            console.log('context', this.props.archInfo.xmlDoc.getAttribute('context'));
            if (!parentId) {
                this.notification.add(_t("Parent ID not found in context"), { type: 'warning' });
                return;
            }

            // Call backend method to search, duplicate and link
            const result = await rpc("/web/dataset/call_kw", {
                model: 'lingjack.list.scanner.base',
                method: 'scan_and_duplicate_record',
                args: [modelName, barcodeValue, parentId,parent_field],
                kwargs: {},
            });

            if (result.status === 'success') {
                this.notification.add(result.message || _t("Record duplicated successfully"), { 
                    type: 'success' 
                });
                // Reload the list to show the new record
                // For one2many fields, reload the list's root model
                const list = this.props.list;
                if (list && list.model && list.model.root) {
                    // Reload the root model (similar to how controller does it)
                    const currentOffset = list.offset || 0;
                    const currentLimit = list.limit || 80;
                    await list.model.root.load();
                } else {
                    // Fallback: reload the list directly
                    await list.load();
                }
                // Trigger a render to update the UI
                this.render();
            } else if (result.status === 'not_found') {
                this.notification.add(result.message || _t("No record found"), { 
                    type: 'warning' 
                });
            } else {
                this.notification.add(result.message || _t("Error processing scan"), { 
                    type: 'danger' 
                });
            }
        } catch (error) {
            console.error("Error handling scan result:", error);
            this.notification.add(_t("Error processing scan: ") + error, { type: 'danger' });
        }
    },
});

// Patch ViewButton to support onClick from clickParams
patch(ViewButton.prototype, {
    async onClick(ev) {
        const hasCustomClick =
            this.clickParams &&
            typeof this.clickParams.onClick === "function";

        if (!hasCustomClick) {
            // No custom handler: keep default behavior
            return super.onClick(ev);
        }

        if (this.props.tag === "a") {
            ev.preventDefault();
        }

        /**
         * IMPORTANT:
         * Let the original ViewButton logic run first so that
         * `clickParams.special` (e.g., `special: 'save'`) is handled
         * and the current record is saved before opening the scanner.
         */
        const result = await super.onClick(ev);

        // After the record is saved, run the custom onClick (open scanner)
        await this.clickParams.onClick();

        return result;
    },
});


