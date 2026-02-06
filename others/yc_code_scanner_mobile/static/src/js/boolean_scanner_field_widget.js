/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { CodeDialog } from "../core/qrcode/code_dialog";


export class BooleanScannerField extends Component {
    static template = "yc_code_scanner_mobile.BooleanScannerField";
    static components = { CheckBox };
    static props = {
        ...standardFieldProps,
        accepted_barcode_field: { type: String, optional: true },
        action_perfom_on_successfull: { type: String, optional: true },
        action_perfom_on_failure: { type: String, optional: true },
        active_model: { type: String, optional: true },
    };

    setup() {
        this.state = useState({});
        this.notification = useService('notification');
        this.dialogService = useService('dialog');
        this.orm = useService("orm");
        useRecordObserver((record) => {
            this.state.value = record.data[this.props.name];
        });
    }

    /**
     * @param {boolean} newValue
     */

    async updateFieldValue(qrCodeMessage) {
        if (this.props.record.data[this.props.accepted_barcode_field] == qrCodeMessage){
            this.props.record.update({ [this.props.name]: true });
            if (this.props.action_perfom_on_successfull){
                if (this.props.active_model){
                    await this.orm.call(
                        this.props.active_model,
                        this.props.action_perfom_on_successfull,
                        [this.props.record.model.config.resId]
                    );
                }
                else{
                    await this.orm.call(
                        this.props.record.model.config.resModel,
                        this.props.action_perfom_on_successfull,
                        [this.props.record.model.config.resId]
                    );
                }
            }
        }
        else{
            this.props.record.update({ [this.props.name]: false });
            if (this.props.action_perfom_on_failure){
                if (this.props.active_model){
                    await this.orm.call(
                        this.props.active_model,
                        this.props.action_perfom_on_failure,
                        [this.props.record.model.config.resId]
                    );
                }
                else{
                    await this.orm.call(
                        this.props.record.model.config.resModel,
                        this.props.action_perfom_on_failure,
                        [this.props.record.model.config.resId]
                    );
                }
            }
        }
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

export const booleanScannerField = {
    component: BooleanScannerField,
    supportedOptions: [
        {
            label: _t("Accepted Barcode Field"),
            name: "accepted_barcode_field",
            type: "string",
        },
        {
            label: _t("Action To be perfom on successfull matching of Barcode/Qr code"),
            name: "action_perfom_on_successfull",
            type: "string",
        },
        {
            label: _t("Action To be perfom on unsuccessfull matching of Barcode/Qr code"),
            name: "action_perfom_on_failure",
            type: "string",
        },
        {
            label: _t("Action To be perfom on which model"),
            name: "active_model",
            type: "string",
        },
    ],
    displayName: _t("Checkbox"),
    supportedTypes: ["boolean"],
    isEmpty: () => false,
    extractProps: ({ attrs, options }) => ({
        accepted_barcode_field: options.accepted_barcode_field,
        action_perfom_on_successfull: options.action_perfom_on_successfull,
        action_perfom_on_failure: options.action_perfom_on_failure,
        active_model: options.active_model,
    }),
};

registry.category("fields").add("yc_boolean_scanner", booleanScannerField);
