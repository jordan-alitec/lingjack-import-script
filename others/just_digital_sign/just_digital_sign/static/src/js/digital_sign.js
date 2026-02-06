/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { useService } from "@web/core/utils/hooks";
import { imageUrl } from "@web/core/utils/urls";
import { isBinarySize } from "@web/core/utils/binary";
import { fileTypeMagicWordMap, imageCacheKey } from "@web/views/fields/image/image_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { NameAndSignature } from "@web/core/signature/name_and_signature";
import { Component, useState , onMounted} from "@odoo/owl";
import { user } from "@web/core/user";

const placeholder = "/web/static/img/placeholder.png";

export class DigitalSignField extends Component {
    static template = "web.digitalSignField";
    static props = {
        ...standardFieldProps,
        defaultFont: { type: String },
        fullName: { type: String, optional: true },
        signatureField: { type: String, optional: true },
        height: { type: Number, optional: true },
        width: { type: Number, optional: true },
        signState: { type: String, optional: true },
        signStateValue: { type: String, optional: true },

    };

    setup() {
        this.displaySignatureRatio = 1;

        this.dialogService = useService("dialog");
        this.state = useState({
            isValid: true,
            showImage: false,
        });

        const { resId, resModel, signName } = this.getSignRes();
        this.resId = resId;
        this.resModel = resModel;
        this.signName = signName;

        onMounted(() => {
			if (this.value && isBinarySize(this.value)) this.state.showImage = true;
            if (this.props.signState != undefined && this.props.record.data[this.props.signState] != false) this.state.showImage = true;
        });
    }

    get rawCacheKey() {
        return this.props.record.data.write_date;
    }

    get getUrl() {
        const { fullName, name } = this.props;
        if (fullName || (this.value && isBinarySize(this.value))) {
            this.state.showImage = true;
            return imageUrl(this.resModel, this.resId, this.props.signatureField || name, { unique: this.rawCacheKey });
        } else {
            // Use magic-word technique for detecting image type
            const magic = fileTypeMagicWordMap[this.value[0]] || "png";
            this.state.showImage = true;
            return `data:image/${magic};base64,${this.props.record.data[this.props.name]}`;
        }
        this.state.showImage = false;
        return placeholder;
    }

    get sizeStyle() {
        let { width, height } = this.props;

        if (!this.value) {
            if (width && height) {
                width = Math.min(width, this.displaySignatureRatio * height);
                height = width / this.displaySignatureRatio;
            } else if (width) {
                height = width / this.displaySignatureRatio;
            } else if (height) {
                width = height * this.displaySignatureRatio;
            }
        }

        let style = "";
        if (width) {
            style += `width:${width}px; max-width:${width}px;`;
        }
        if (height) {
            style += `height:${height}px; max-height:${height}px;`;
        }
        return style;
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    getSignRes() {
        var resUserId = false;
        const { fullName, record } = this.props;
        let signName;
        if (fullName) {
            const fullNameData = record.data[fullName];
            if (record.fields[fullName].type === "many2one") {
                // If m2o is empty, it will have falsy value in recordData
                signName = fullNameData && fullNameData[1];
                resUserId = fullNameData[0]
            } else {
                //signName = fullNameData;
                signName = user.name;
            }
            return { 'resId': resUserId, 'resModel': 'res.users', 'signName': signName };
        } else {
            signName = user.name;
            return { 'resId': record.resId, 'resModel': record.resModel, 'signName': signName };
        }
    }

    onClickSignature() {
        if (!this.props.readonly) {
            const nameAndSignatureProps = {
                mode: "auto",
                displaySignatureRatio: 3,
                signatureType: "signature",
                noInputName: true,
            };

            const { fullName, record } = this.props;
            let defaultName = this.signName === "" ? undefined : this.signName;
            // if (fullName) {
            //     defaultName = record.data.name;
            //     //defaultName = this.signName === "" ? undefined : this.signName;
            // }

            nameAndSignatureProps.defaultFont = this.props.defaultFont;

            const dialogProps = {
                defaultName,
                nameAndSignatureProps,
                uploadSignature: (signature) => this.uploadSignature(signature),
            };
            this.dialogService.add(SignatureDialog, dialogProps);
        }
    }

    onLoadFailed() {
        this.state.isValid = false;
        this.state.showImage = false;
        // this.notification.add(_t("Could not display the selected image"), {
        //     type: "danger",
        // });
    }

    /**
     * Upload the signature image if valid and close the dialog.
     *
     * @private
     */
    async uploadSignature({ signatureImage }) {
        const file = signatureImage.split(",")[1];
        var {name, signatureField} = this.props;
    
        if (signatureField) name = signatureField;
        var writeOp = 'write';
        if (this.resModel == 'res.users') writeOp = 'writeSign';
        await this.env.services.orm.call(this.resModel, writeOp, [[this.resId], {
            [name]: file,
        }]);

        await this.props.record.load();
        this.state.showImage = true;
        if (this.props.signState != undefined) {
            if (this.props.signStateValue == "default") this.props.signStateValue = this.signName;
            var sign_state = { [this.props.signState]: this.props.signStateValue };
            this.props.record.data[this.props.signState] = this.props.signStateValue;
            this.props.record.update({ [this.props.signState]: this.props.signStateValue });
        }            
        // this.props.model.notify();
    }
}

export const digitalSignField = {
    component: DigitalSignField,
    fieldDependencies: [{ name: "write_date", type: "datetime" }],
    supportedOptions: [
        {
            label: _t("Prefill with"),
            name: "full_name",
            type: "field",
            availableTypes: ["char", "many2one"],
            help: _t("The selected field will be used to pre-fill the signature"),
        },
        {
            label: _t("Signed State Field"),
            name: "sign_state",
            type: "selection",
            help: _t("The selected field will be used to state the signature"),
        },
        {
            label: _t("Default font"),
            name: "default_font",
            type: "string",
        },
        {
            label: _t("Size"),
            name: "size",
            type: "selection",
            choices: [
                { label: _t("Small"), value: "[0,90]" },
                { label: _t("Medium"), value: "[0,180]" },
                { label: _t("Large"), value: "[0,270]" },
            ],
        },
        {
            label: _t("Preview image field"),
            name: "signatureField",
            type: "field",
            availableTypes: ["binary"],
        },
    ],
    extractProps: ({ attrs, options }) => ({
        defaultFont: options.default_font || "",
        fullName: options.full_name,
        signState: options.signState? options.signState[0] || undefined : undefined,
        signStateValue: options.signState ? options.signState[1] || undefined : undefined,
        signatureField: options.signatureField,
        height: options.size ? options.size[1] || undefined : attrs.height,
        width: options.size ? options.size[0] || undefined : attrs.width,
    }),
};

registry.category("fields").add("digitalsign", digitalSignField);