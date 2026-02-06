/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import {
    many2ManyTagsField,
    Many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";
import { useChildRef, useService } from "@web/core/utils/hooks";
import { TagsList } from "@web/core/tags_list/tags_list";
import { AvatarMany2XAutocomplete } from "@web/views/fields/relational_utils";
import { CodeDialog } from "../core/qrcode/code_dialog";

export class Many2ManyTagsCodeField extends Many2ManyTagsField {
    static template = "yc_code_scanner_mobile.Many2ManyTagsCodeField";
    static components = {
        Many2XAutocomplete: AvatarMany2XAutocomplete,
        TagsList,
    };
    static props = {
        ...Many2ManyTagsField.props,
        withCommand: { type: Boolean, optional: true },
    };

    setup() {
        super.setup();
        if (this.props.qrCodeMessage){
            this.state.qrCodeMessage = this.props.qrCodeMessage;
        }
        this.autocompleteContainerRef = useChildRef();
        this.notification = useService('notification');
        this.dialogService = useService('dialog');
    }

    getTagProps(record) {
        return {
            ...super.getTagProps(record),
        };
    }

    async search_record(code) {
        const results = await this.orm.call(this.relation, "name_search", [], {
            name: code,
            args: this.getDomain(),
            operator: "=",
            limit: 2, // If one result we set directly and if more than one we use normal flow so no need to search more
            context: this.context,
        });
        return results.map((result) => {
            const [id, displayName] = result;
            return {
                id,
                name: displayName,
            };
        });
    }

    async updateFieldValue(qrCodeMessage) {
        const results = await this.search_record(qrCodeMessage);
        const records = results.filter((r) => !!r.id);
        if (records.length === 1) {
            this.update([{ id: records[0].id, name: records[0].name }]);
        } else {
            this.notification.add("Code detected but record not found: " + qrCodeMessage, { type: 'warning' });
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

export const many2ManyTagsCodeField = {
    ...many2ManyTagsField,
    component: Many2ManyTagsCodeField,
    extractProps({ viewType }, dynamicInfo) {
        const props = many2ManyTagsField.extractProps(...arguments);
        props.withCommand = viewType === "form" || viewType === "list";
        props.domain = dynamicInfo.domain;
        return props;
    },
};

registry.category("fields").add("yc_many2many_tags_code_scanner", many2ManyTagsCodeField);