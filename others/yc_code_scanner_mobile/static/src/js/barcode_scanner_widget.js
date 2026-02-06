/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useInputField } from "@web/views/fields/input_field_hook";
import { _t } from "@web/core/l10n/translation";
import { Component,useRef,useState,markup,onWillRender } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog, AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { renderToMarkup } from '@web/core/utils/render';
import { CodeDialog } from "../core/qrcode/code_dialog";


export class BarcodeScannerWidget extends Component {
    static template = "yc_code_scanner_mobile.widget_qrcode_scanner";

    setup() {
        if (this.props.qrCodeMessage){
            this.state.qrCodeMessage = this.props.qrCodeMessage;
        }
        this.state = useState({
            deviceUid: '',
            codeType: 0,
            barcodeReader: '',
        });
        this.notification = useService('notification');
        this.dialogService = useService('dialog');
        useInputField({
            getValue: () => this.formattedValue,
            refName: "barcodeChar",
            parse: (v) => v,
        });
    }

    get formattedValue() {
        return this.props.record.data[this.props.name] || '';
    }

    updateFieldValue(qrCodeMessage) {
        this.props.record.update({ [this.props.name]: qrCodeMessage });
    }

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
}
BarcodeScannerWidget.props = {
    ...standardFieldProps,
    value: { type: Function, optional: true },
    deviceUid: { type: String, optional: true },
    codeType: { type: Boolean, optional: true },
    barcodeReader: { type: String, optional: true },
    qrCodeMessage: { type: String, optional: true },
}
export const BarcodeScanner = {
    component: BarcodeScannerWidget,
    supportedTypes: ["char"],
};
registry.category('fields').add('yc_char_barcode_scanner', BarcodeScanner);

