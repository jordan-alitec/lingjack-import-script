/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, useRef, useState } from "@odoo/owl";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";

export class PdfFormTemplateTopBar extends Component {
    static template = "pdfForm.TemplateTopBar";
    static props = {
        PdfFormTemplate: Object,
        onTemplateNameChange: Function,
    };

    setup() {
        this.displayNameInput = useRef("display-name");
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.fileInputRef = useRef("fileInput");
        this.http = useService("http");
        this.state = useState({
            isUploading: false,
        });
        this.template = this.props.PdfFormTemplate.xmlDoc.getElementsByTagName("pdfTemplate");
    }

    changeInputSize() {
        const el = this.displayNameInput.el;
        if (el) {
            el.size = el.value.length + 1;
        }
    }

    get displayNameSize() {
        return this.props.PdfFormTemplate.name.length + 1;
    }

    async onFileUploaded(data) {
        this.fileInputRef.el.click();
        //const { id: attachmentId } = await this.attachmentUploader.uploadData(data);
    }

    async onFileChange(ev) {
        if (!ev.target.files.length) {
            return;
        }
        const { target } = ev;
        for (const file of ev.target.files) {
            if (!checkFileSize(file.size, this.notification)) {
                return null;
            }
            this.state.isUploading = true;
            const data = await getDataURLFromFile(file);
            if (!file.size) {
                console.warn(`Error while uploading file : ${file.name}`);
                this.notification.add(_t("There was a problem while uploading your file."), {
                    type: "danger",
                });
            }
            try {
                await this.orm.call("ir.attachment", "checkUnlink", [this.props.PdfFormTemplate.viewId]);
                const fileData = await this.http.post(
                    "/web/binary/upload_attachment",
                    {
                        csrf_token: odoo.csrf_token,
                        ufile: [file],
                        model: "ir.ui.view",
                        id: this.props.PdfFormTemplate.viewId,
                    },
                    "text"
                );
                const parsedFileData = JSON.parse(fileData);
                if (parsedFileData.error) {
                    throw new Error(parsedFileData.error);
                }
                this.notification.add(_t("File uploaded successfully"), { type: "success" });
                this.props.PdfFormTemplate.id = parsedFileData[0].id;
                this.props.PdfFormTemplate.name = parsedFileData[0].filename;
                this.orm.call("ir.attachment", "write", [[this.props.PdfFormTemplate.id], { public: true }]);

                if (this.template != null) {
                    if (this.template[0] != undefined) {
                        this.template[0].textContent = this.props.PdfFormTemplate.name;
                        this.template[0].setAttribute("pdfid", this.props.PdfFormTemplate.id);
                    } else {
                        this.props.PdfFormTemplate.xmlDoc.innerHTML = this.props.PdfFormTemplate.xmlDoc.innerHTML + "<pdfTemplate pdfid='" + this.props.PdfFormTemplate.id + "'>" + this.props.PdfFormTemplate.name + "</pdfTemplate>"; 
                    }

                }
                this.saveChanges(this.props.PdfFormTemplate.viewId, { 'arch': this.props.PdfFormTemplate.xmlDoc.outerHTML });
                window.location.reload();

            } finally {
                this.state.isUploading = false;
            }
        }
        target.value = null;
    }

    editDisplayName() {
        this.fileInputRef.el.click();
        // this.displayNameInput.el.focus();
        // this.displayNameInput.el.select();
    }

    onKeyDown(e) {
        if (e.key === "Enter") {
            this.displayNameInput.el.blur();
        }
    }

    onTemplatePropertiesClick() {
        this.action.doAction({
            name: "Edit Template Form",
            type: "ir.actions.act_window",
            res_model: "ir.ui.view",
            res_id: this.props.PdfFormTemplate.viewId,
            views: [[false, "form"]],
        });
    }

    onChange(key, value) {
        this.props.PdfFormTemplate.activeActions[key] = !value;
        const pdfform = this.props.PdfFormTemplate.xmlDoc;
        if (key === "template") pdfform.setAttribute("template", value ? "0" : "1");
        if (key === "edit") pdfform.setAttribute("edit", value ? "0" : "1");
        this.saveChanges(this.props.PdfFormTemplate.viewId, { 'arch': pdfform.outerHTML });
    }

    async saveChanges(resId, changes) {
        const res = await this.orm.call("ir.ui.view", "write", [[resId], changes]);
        if (res) {
            this.notification.add(_t("Saved"), { type: "success" });
        }
    }
}
