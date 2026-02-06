/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useInputField } from "@web/views/fields/input_field_hook";
import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { ScannerDialog } from "./scanner_dialog";

export class InlineBarcodeScannerWidget extends Component {
    static template = "inline_barcode_scanner.InlineBarcodeScannerWidget";

    setup() {
        this.state = useState({
            deviceUid: '',
            codeType: 0,
            barcodeReader: '',
        });
        this.notification = useService('notification');
        this.dialogService = useService('dialog');
        useInputField({
            getValue: () => this.formattedValue,
            refName: "barcodeInput",
            parse: (v) => v,
        });
    }

    get formattedValue() {
        return this.props.record.data[this.props.name] || '';
    }

    updateFieldValue(qrCodeMessage) {
        this.props.record.update({ [this.props.name]: qrCodeMessage });
    }

    async onScanButtonClick() {
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
                onResult: (result) => this.updateFieldValue(result),
                onError: (error) => {
                    console.log("QR code not detected", error);
                    this.notification.add(_t("QR code not detected"), { type: 'warning' });
                },
            });
        } catch (err) {
            this.notification.add(_t("Camera Not Found: ") + err, { type: 'warning' });
        }
    }
}

InlineBarcodeScannerWidget.props = {
    ...standardFieldProps,
};

export const InlineBarcodeScanner = {
    component: InlineBarcodeScannerWidget,
    supportedTypes: ["char"],
};

registry.category('fields').add('inline_barcode_scanner', InlineBarcodeScanner);

