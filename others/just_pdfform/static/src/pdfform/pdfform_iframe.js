/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { renderToString } from "@web/core/utils/render";
import { shallowEqual } from "@web/core/utils/arrays";
import { normalizePosition, startResize } from "./utils";
import { FieldsCustomPopover } from "./Fields_custom_popover";
import { PDFIframe } from "./PDF_iframe";
import { EditablePDFIframeMixin } from "./editable_pdf_iframe_mixin";
import { Deferred } from "@web/core/utils/concurrency";
import { isMobileOS } from "@web/core/browser/feature_detection";

export class PdfFormIframe extends EditablePDFIframeMixin(PDFIframe) {
    /**
     * Renders custom elements inside the PDF.js iframe
     * @param {HTMLIFrameElement} iframe
     * @param {Document} root
     * @param {Object} env
     * @param {Object} owlServices
     * @param {Object} props
     */
    constructor(root, env, owlServices, props) {
        super(root, env, owlServices, props);
        this.deletedpdfFieldIds = [];
        this.closePopoverFns = {};

        /**
         * This is used to keep track of the sign items that are currently being
         * fetched from the server. This is used to ensure that the sign item
         * on which a click event is triggered is completely loaded before
         */
        this.negativeIds = {};
    }

    get allowEdit() {
        return this.props.defView;
    }

    renderSidebar() {
        super.renderSidebar();
        if (this.allowEdit && !isMobileOS()) {
            const sideBar = renderToString("pdfForm.fieldsTypesSidebar", {
                fields: this.props.fields,
            });
            this.root.body.insertAdjacentHTML("afterbegin", sideBar);
        }
    }

    registerDragEventsForpdfField(pdfField) {
        super.registerDragEventsForpdfField(pdfField);
        const display = pdfField.el.querySelector(".o_sign_item_display");
        display.addEventListener("click", (e) => this.openpdfFieldPopup(pdfField, e.ctrlKey));
    }

    /**
     * Handles opening and closing of popovers in template edition
     * @param {pdfField} pdfField
     */
    async openpdfFieldPopup(pdfField, bool) {
        this.preChange(pdfField, bool);

        const shouldOpenNewPopover = !(pdfField.data.props.id in this.closePopoverFns);
        this.closePopover();
        if (shouldOpenNewPopover) {
            if (pdfField.data.props.id in this.negativeIds) {
                await this.negativeIds[pdfField.data.id];
            }
            const closeFn = this.popover.add(
                pdfField.el,
                FieldsCustomPopover,
                {
                    name: pdfField.data.props.fieldInfo.name,
                    invisible: pdfField.data.props.fieldInfo.invisible,
                    required: pdfField.data.props.fieldInfo.required,
                    readonly: pdfField.data.props.fieldInfo.readonly,
                    domain: pdfField.data.props.fieldInfo.domain,
                    context: pdfField.data.props.fieldInfo.context,
                    placeholder: pdfField.data.props.fieldInfo.placeholder,
                    type: pdfField.data.props.fieldInfo.type,
                    option_ids: pdfField.data.props.fieldInfo.option_ids,
                    position: pdfField.data.props.fieldInfo.position,
                    options: pdfField.data.props.fieldInfo.options,
                    widget: pdfField.data.props.fieldInfo.widget,
                    widgets: [],
                    selection: this.preList,
                    onValidate: (data) => {
                        this.updatepdfField(pdfField, data);
                        this.closePopover();
                    },
                    onDelete: () => {
                        this.closePopover();
                        this.deletepdfField(pdfField);
                    },
                    onClose: () => {
                        this.closePopover();
                    },
                    saveChanges: (keep) => {
                        if (!keep) this.closePopover();
                        this.saveChanges();
                    },                    
                },
                {
                    position: "right",
                    onClose: () => {
                        this.closePopoverFns = {};
                    },
                    closeOnClickAway: false,
                    popoverClass: "sign-popover",
                }
            );
            this.closePopoverFns[pdfField.data.props.id] = {
                close: closeFn,
                pdfField,
            };
        }

    }

    /**
     * Closes all open popovers
     */
    closePopover() {
        if (Object.keys(this.closePopoverFns)) {
            for (const id in this.closePopoverFns) {
                this.closePopoverFns[id].close();
            }
            this.closePopoverFns = {};
        }
    }

    /**
     * Updates the sign item, re-renders it and saves the template in case there were changes
     * @param {pdfField} pdfField
     * @param {Object} data
     */
    updatepdfField(pdfField, data) {
        const soureData = pdfField.data.props.fieldInfo;
        const changes = Object.keys(data).reduce((changes, key) => {
            if (key in soureData) {
                if (Array.isArray(data[key])) {
                    if (!shallowEqual(soureData[key], data[key])) {
                        changes[key] = data[key];
                    }
                } else if (soureData[key] !== data[key]) {
                    changes[key] = data[key];
                }
            }
            return changes;
        }, {});
        if (Object.keys(changes).length) {
            Object.assign(soureData, changes);
            Object.assign(pdfField.data.props, {
                readonly: data.readonly,
                invisible: data.invisible,
                required: data.required,
            });
            const pageNumber = soureData.position.page;
            const page = this.getPageContainer(pageNumber);
            const id = pdfField.el.dataset.id;
            pdfField.el.parentElement.removeChild(pdfField.el);
            this.renderpdfField(pdfField, page, pageNumber).then((el) => {
                el.dataset.id = id;
                this.pdfFields[pageNumber][id] = {
                    data: pdfField.data,
                    el: el,
                };
                this.enableCustom(this.pdfFields[pageNumber][id]);
                this.refreshpdfFields();
                this.saveChanges();
            })
        }
    }

    /**
     * Deletes a sign item from the template
     * @param {pdfField} pdfField
     */
    deletepdfField(pdfField) {
        this.deletedpdfFieldIds.push(pdfField.el.dataset.id);
        super.deletepdfField(pdfField);
    }

    /**
     * Enables resizing and drag/drop for sign items
     * @param {pdfField} pdfField
     */
    enableCustom(pdfField) {
        if (this.allowEdit) {
            startResize(pdfField, this.onResizeItem.bind(this));
            this.registerDragEventsForpdfField(pdfField);
        }
    }

    /**
     * Extends the rendering context of the sign item based on its data
     * @param {pdfField.data} pdfField
     * @returns {Object}
     */
    getContext(pdfField) {
        var options = pdfField.props.fieldInfo.position;
        const normalizedPosX =
            Math.round(normalizePosition(options.posX, options.width) * 1000) / 1000;
        const normalizedPosY =
            Math.round(normalizePosition(options.posY, options.height) * 1000) / 1000;

        Object.assign(pdfField.props, {
            editMode: true,
            required: Boolean(pdfField.props.fieldInfo.required),
            placeholder: this.props.defView ? pdfField.props.fieldInfo.placeholder || pdfField.props.fieldInfo.name || "" : "",
            style: `top: ${normalizedPosY * 100}%; left: ${normalizedPosX * 100}%;
                    width: ${options.width * 100}%; height: ${options.height * 100}%;
                    text-align: ${options.alignment}; position: absolute;`,
        });
        return pdfField;
    }

    /**
     * Hook executed before rendering the sign items and the sidebar
     */
    preRender() {
        super.preRender();
        if (this.allowEdit && !isMobileOS()) {
            const outerContainer = this.root.querySelector("#outerContainer");
            Object.assign(outerContainer.style, {
                width: "auto",
                marginLeft: "14rem",
            });
            outerContainer.classList.add("o_sign_field_type_toolbar_visible");
            this.root.dispatchEvent(new Event("resize"));
        }
        // else if (!this.allowEdit) {
        //     const div = this.root.createElement("div");
        //     Object.assign(div.style, {
        //         position: "absolute",
        //         top: 0,
        //         left: 0,
        //         width: "100%",
        //         height: "100%",
        //         zIndex: 110,
        //         opacity: 0.75,
        //     });
        //     this.root.querySelector("#viewer").style.position = "relative";
        //     this.root.querySelector("#viewer").prepend(div);
        // }
        //this.insertRotatePDFButton();
    }

    insertRotatePDFButton() {
        const printButton = this.root.querySelector("#print");
        const button = this.root.createElement("button");
        button.setAttribute("id", "pageRotateCw");
        button.className = "toolbarButton o_sign_rotate rotateCw";
        button.title = _t("Rotate Clockwise");
        printButton.parentNode.insertBefore(button, printButton);
        button.addEventListener("click", (e) => this.rotatePDF(e));
    }

    postRender() {
        super.postRender();
        if (this.allowEdit) {
            const viewerContainer = this.root.querySelector("#viewerContainer");
            // close popover when clicking outside of a sign item
            viewerContainer.addEventListener(
                "click",
                (e) => {
                    if (!e.target.closest(".o_sign_item_display")) {
                        this.closePopover();
                    }
                },
                { capture: true }
            );
            this.root.addEventListener("keyup", (e) => this.handleKeyUp(e));
        }
    }

    handleKeyUp(e) {
        if (e.key === "Delete" && Object.keys(this.closePopoverFns)) {
            //delete any element that has its popover open
            for (const id in this.closePopoverFns) {
                const { close, pdfField } = this.closePopoverFns[id];
                typeof close === "function" && close();
                this.deletepdfField(pdfField);
            }
            this.closePopoverFns = {};
        }
    }

    async saveChanges() {
        await this.props.saveTemplate();
        this.deletedpdfFieldIds = [];
    }

    preChange(elem, bool) {
        if (this.preList.length > 0 && !bool) {//如果数组里有值并且没有按住ctrl
            this.preList.forEach(function (item) {
                item.el.style.border = "none";//让数组里的每一项的样式都清空
            })
            this.preList.length = 0;//让数组清零
        }
        this.preList.push(elem);//把当前点击的这一项添加到数组里,设置样式,如果按住ctrl,直接把每一项设置样式
        elem.el.style.border = "2px solid #FF0000"
    }
}
