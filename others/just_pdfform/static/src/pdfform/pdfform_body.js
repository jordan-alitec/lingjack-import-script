/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { PdfFormIframe } from "./pdfform_iframe";
import { PdfFormTemplateTopBar } from "./pdfform_top_bar";
import { Component, useRef, useEffect, onWillUnmount } from "@odoo/owl";
import { buildPDFViewerURL } from "./utils";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { renderToString } from "@web/core/utils/render";

export class PdfFormTemplateBody extends Component {
    static template = "pdfForm.TemplateBody";
    static components = {
        PdfFormTemplateTopBar,
    };
    static props = {
        PdfFormTemplate: Object,
        fields: Object,
        pdfFields: Object,
        attachmentLocation: String,
        childEnv: Object,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.popover = useService("popover");
        this.dialog = useService("dialog");
        this.PDFIframe = useRef("PDFIframe");
        this.PDFViewerURL = buildPDFViewerURL(this.props.attachmentLocation, this.env.isSmall);
        this.defView = this.props.PdfFormTemplate.editor_view;
        useEffect(
            () => {
                return this.waitForPDF();
            },
            () => []
        );
        onWillUnmount(() => {
            if (this.iframe) {
                this.saveTemplate();
                this.iframe.unmount();
                this.iframe = null;
            }
        });
    }

    waitForPDF() {
        this.PDFIframe.el.onload = () => setTimeout(() => this.doPDFPostLoad(), 1);
    }

    doPDFPostLoad() {
        this.preventDroppingImagesOnViewerContainer();
        this.iframe = new PdfFormIframe(
            this.PDFIframe.el.contentDocument,
            this.props.childEnv.env,
            {
                orm: this.orm,
                popover: this.popover,
                dialog: this.dialog,
            },
            {
                fields: this.props.fields,
                pdfFields: this.props.pdfFields,
                models: this.props.childEnv.models,
                resModel: this.props.childEnv.resModel,
                defView: this.defView,
                template: this.props.PdfFormTemplate.activeActions.template,
                hasTemplate: this.props.PdfFormTemplate.hasTemplate,
                saveTemplate: () => this.saveTemplate(),
                rotatePDF: () => this.rotatePDF(),
            }
        );
    }

    /**
     * Prevents opening files in the pdf js viewer when dropping files/images to the viewerContainer
     * Ref: https://stackoverflow.com/a/68939139
     */
    preventDroppingImagesOnViewerContainer() {
        const viewerContainer = this.PDFIframe.el.contentDocument.querySelector("#viewerContainer");
        viewerContainer.addEventListener(
            "drop",
            (e) => {
                if (e.dataTransfer.files && e.dataTransfer.files.length) {
                    e.stopImmediatePropagation();
                    e.stopPropagation();
                }
            },
            true
        );
    }

    onTemplateNameChange(e) {
        const value = e.target.value;
        if (value != "") {
            this.props.PdfFormTemplate.name = value;
            this.saveTemplate(this.props.PdfFormTemplate);
        }
    }

    async saveTemplate(newTemplateName) {
        if (this.defView) {
            if (newTemplateName) {
                this.props.PdfFormTemplate = newTemplateName;
            }
            const updatedPdfFields = this.prepareTemplateData();
            var pdfFormReadonly = "";
            for (const key in this.props.PdfFormTemplate.activeActions) {
                if (this.props.PdfFormTemplate.activeActions[key] === false) pdfFormReadonly += key+'="0" ';
            };
            var pdfFormdef = '<pdfForm ' + pdfFormReadonly + '>\n\t<pdfTemplate pdfid="'+ this.props.PdfFormTemplate.id +'">'+ this.props.PdfFormTemplate.name +'</pdfTemplate>\n';
            $.map(updatedPdfFields, function (field) {
                pdfFormdef +="\t" + field +"\n";
            });
            pdfFormdef += "</pdfForm>";
            const newId2ItemIdMap = await this.orm.call("ir.ui.view", "write", [[this.props.PdfFormTemplate.viewId], { arch: pdfFormdef }]);

            //this.notification.add(_t("Saved"), { type: "success" });
        }
    }

    prepareTemplateData() {
        const updatedPdfFields = [];
        const Id2UpdatedItem = {};
        const items = this.iframe?.pdfFields ?? {};
        var exceptKey = /.*(name|options|position|domain|context|widget|groups|groups_edit|invisible|required|readonly)$/;

        for (const page in items) {
            for (const id in items[page]) {
                var field = "<field ";
                var viewXml = "";
                const pdfField = items[page][id].data;
                const newObj = Object.entries(pdfField.props.fieldInfo).reduce((acc, [key, value]) => {
                    if (value !== '' && value !== null && value !== undefined && value != '{}' && value != '[]' ) {  //&& Object.keys(value).length > 0
                        if (exceptKey.test(key)) {
                            acc[key] = value;
                            if ( "|invisible|required|readonly".includes(key)  && pdfField.props.fieldInfo.attrs[key] != undefined) value = pdfField.props.fieldInfo.attrs[key];
                            field += key + '="' + (typeof value == "object" ? JSON.stringify(value).replace(/"/g,"'") : value) + '" ';
                        }
                        if (key === "views") {
                            for (let key in value) {
                              viewXml += value[key].xmlDoc.outerHTML;
                            }
                        }
                    }
                    return acc;
                }, {});
                field += (viewXml ==="") ? "/>" : ">" + viewXml + "</field>";
                updatedPdfFields.push(field);
            }
        }
        return updatedPdfFields;
    }

    async rotatePDF() {
        const result = await this.orm.call("ir.ui.view", "rotate_pdf", [
            this.props.PdfFormTemplate.id,
        ]);
        if (!result) {
            this.showBlockedTemplateDialog();
        }

        return result;
    }

    showBlockedTemplateDialog() {
        this.dialog.add(AlertDialog, {
            confirm: () => {
                this.props.goBackToKanban();
            },
            body: _t("Somebody is already filling a document which uses this template"),
        });
    }
}
