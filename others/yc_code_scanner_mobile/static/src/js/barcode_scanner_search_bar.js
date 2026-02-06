/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useService } from "@web/core/utils/hooks";
import { CodeDialog } from "../core/qrcode/code_dialog";

patch(SearchBar.prototype, {
    setup() {
        super.setup();
        if (this.props.qrCodeMessage){
            this.state.qrCodeMessage = this.props.qrCodeMessage;
        }
        this.notification = useService('notification');
        this.dialogService = useService('dialog');
    },

    async updateFieldValue(qrCodeMessage) {
        const query = qrCodeMessage;
        if (query.trim()) {
            this.computeState({ query, expanded: [], focusedIndex: 0, subItems: [] });
            const focusedItem = this.items[this.state.focusedIndex];
            if (this.state.query.length && focusedItem) {
                this.selectItem(focusedItem);
            }
        } else if (this.items.length) {
            this.resetState();
        }
    },

    async onConfigButtonClick() {
        try {
            const devices = await window.__Html5QrcodeLibrary__.Html5Qrcode.getCameras();
            const supportedCodes = [
                { id: 1, label: 'code_128_reader', value:'Code 128' },
                { id: 2, label: 'ean_reader', value:'EAN' },
                { id: 3, label: 'ean_8_reader', value:'EAN-8' },
                { id: 4, label: 'code_39_reader', value:'Code 39' },
                { id: 5, label: 'code_39_vin_reader', value:'Code 39 VIN' },
                { id: 6, label: 'codabar_reader', value:'Codabar' },
                { id: 7, label: 'upc_reader', value:'UPC' },
                { id: 8, label: 'upc_e_reader', value:'UPC-E' },
                { id: 9, label: 'i2of5_reader', value:'Interleaved 2 of 5' },
                { id: 10, label: '2of5_reader', value:'Standard 2 of 5' },
                { id: 11, label: 'code_93_reader', value:'Code 93' },
                { id: 12, label: 'ean_extended_reader', value:'EAN Extended' },
            ];

            const facingMode = "environment"
            const qrCodeScanner = ''
            const codeType = 0
            const deviceUid = devices[0].id
            const barcodeReader = supportedCodes[0].label

            this.dialogService.add(CodeDialog, {
                facingMode,
                devices, 
                supportedCodes,
                codeType,
                deviceUid,
                barcodeReader,
                qrCodeScanner,
                onResult: (result) => this.updateFieldValue(result),
                onError: (error) => console.log("QR code not detected", error),
            });
        } catch (err) {
            this.notification.add("Camera Not Found: " + err, { type: 'warning' });
        }
    }
});