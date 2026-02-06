/** @odoo-module **/

import { renderToString } from "@web/core/utils/render";
import {
    startHelperLines,
    offset,
    normalizePosition,
    generateRandomId,
    startSmoothScroll,
    startResize,
} from "./utils";
// import { InitialsAllPagesDialog } from "@field/dialogs/initials_all_pages_dialog";
import { isMobileOS } from "@web/core/browser/feature_detection";

/**
 * Mixin that adds edit features into PDF_iframe classes like drag/drop, resize, helper lines
 * Currently, it should be used only for EditWhilefieldingfieldablePDFIframe and fieldTemplateIframe
 * Parent class should implement allowEdit and saveChanges
 *
 * @param { class } pdfClass
 * @returns class
 */
export const EditablePDFIframeMixin = (pdfClass) =>
    class extends pdfClass {
        /**
         * Callback executed when a field item is resized
         * @param {pdfField} pdfField
         * @param {Object} change object with new width and height of field item
         * @param {Boolean} end boolean indicating if the resize is done or still in progress
         */
        onResizeItem(pdfField, change, end = false) {
            if (change.width < 0.05) change.width = 0.05;
            if (change.height < 0.01) change.height = 0.01;
            this.helperLines.show(pdfField.el);
            Object.assign(pdfField.el.style, {
                height: `${change.height * 100}%`,
                width: `${change.width * 100}%`,
            });
            Object.assign(pdfField.data.props.fieldInfo.position, {
                width: change.width,
                height: change.height,
            });
  
            this.updatepdfFieldFontSize(pdfField);
            if (end) {
                this.helperLines.hide();
                this.saveChanges();
            }
        }

        get allowEdit() {}

        /**
         * @override
         */
        renderpdfField() {
            const pdfField = super.renderpdfField(...arguments);
            if (isMobileOS()) {
                for (const node of pdfField.querySelectorAll(
                    ".o_sign_config_handle, .o_resize_handler"
                )) {
                    node.classList.add("d-none");
                }
            }
            return pdfField;
        }

        renderpdfFields() {
            super.renderpdfFields();
            if (this.allowEdit) {
                this.startDragAndDrop();
                this.helperLines = startHelperLines(this.root);
            }
        }

        startDragAndDrop() {
            this.root.querySelectorAll(".page").forEach((page) => {
                page.addEventListener("dragover", (e) => this.onDragOver(e));
                page.addEventListener("drop", (e) => this.onDrop(e));
            });

            this.root.querySelectorAll(".o_sign_field_type_button").forEach((sidebarItem) => {
                sidebarItem.setAttribute("draggable", true);
                sidebarItem.addEventListener("dragstart", (e) => this.onSidebarDragStart(e));
                sidebarItem.addEventListener("dragend", (e) => this.onSidebarDragEnd(e));
            });
        }

        onDragStart(e) {
            const pdfField = e.currentTarget.parentElement.parentElement;
            const page = pdfField.parentElement;
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("page", page.dataset.pageNumber);
            e.dataTransfer.setData("id", pdfField.dataset.id);
            e.dataTransfer.setDragImage(pdfField, 0, 0);
            e.currentTarget.dataset.page = page.dataset.pageNumber;
            e.currentTarget.dataset.id = pdfField.dataset.id;
            // workaround to hide element while keeping the drag image visible
            requestAnimationFrame(() => {
                if (pdfField) {
                    pdfField.style.visibility = "hidden";
                }
            }, 0);
            this.scrollCleanup = startSmoothScroll(
                this.root.querySelector("#viewerContainer"),
                pdfField,
                null,
                this.helperLines
            );
        }

        onDragEnd(e) {
            this.scrollCleanup();
            if (e.currentTarget.dataset.page && e.currentTarget.dataset.id) {
                const initialPage = Number(e.currentTarget.dataset.page);
                const id = Number(e.currentTarget.dataset.id);
                const pdfField = this.pdfFields[initialPage][id];
                const pdfFieldEl = pdfField.el;
                const posX = pdfField.data.props.fieldInfo.position.posX;
                const posY =  pdfField.data.props.fieldInfo.position.posY;

                Object.assign(pdfField.el.style, {
                    top: `${posY * 100}%`,
                    left: `${posX * 100}%`,
                    visibility: "visible",
                });
            }
        }

        onSidebarDragStart(e) {
            const fieldTypeElement = e.currentTarget;
            const firstPage = this.root.querySelector('.page[data-page-number="1"]');
            firstPage.insertAdjacentHTML(
                "beforeend",
                renderToString(
                    "pdfForm.newField",
                    {
                        required: true,
                        editMode: true,
                        readonly: true,
                        updated: true,
                        option_ids: [],
                        options: [],
                        name: fieldTypeElement.dataset.itemName,
                        width: 0.15,
                        height: 0.015,
                        alignment: "center",
                        type:  fieldTypeElement.dataset.itemTypeId,
                        placeholder: fieldTypeElement.dataset.itemName,
                        classes: `o_color_responsible_yellow`,
                        style: `width: 15%; height: 1.5%;`,
                    }
                )
            );
            this.ghostpdfField = firstPage.lastChild;
            e.dataTransfer.setData("typeId", fieldTypeElement.dataset.itemTypeId);
            e.dataTransfer.setData("name", fieldTypeElement.dataset.itemName);
            e.dataTransfer.setDragImage(this.ghostpdfField, 0, 0);
            this.scrollCleanup = startSmoothScroll(
                this.root.querySelector("#viewerContainer"),
                e.currentTarget,
                this.ghostpdfField,
                this.helperLines
            );
            // workaround to set original element to hidden while keeping the cloned element visible
            requestAnimationFrame(() => {
                if (this.ghostpdfField) {
                    this.ghostpdfField.style.visibility = "hidden";
                }
            }, 0);
        }

        onSidebarDragEnd() {
            this.scrollCleanup();
            const firstPage = this.root.querySelector('.page[data-page-number="1"]');
            firstPage.removeChild(this.ghostpdfField);
            this.ghostpdfField = false;
        }

        onDragOver(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
        }

        onDrop(e) {
            e.preventDefault();
            const page = e.currentTarget;
            const textLayer = page.querySelector(".textLayer");
            const targetPage = Number(page.dataset.pageNumber);

            const { top, left } = offset(textLayer);
            const name = e.dataTransfer.getData("name");
            if (name) {
                const id = this.newId(targetPage);
                const newField = this.createpdfFieldDataFromType(name);
                const posX =
                    Math.round(
                        normalizePosition((e.pageX - left) / textLayer.clientWidth, newField.data.width) *
                            1000
                    ) / 1000;
                const posY =
                    Math.round(
                        normalizePosition((e.pageY - top) / textLayer.clientHeight, newField.data.height) *
                            1000
                    ) / 1000;

                Object.assign(newField.data.props.fieldInfo.position, { posX, posY, page: targetPage });

                this.renderpdfField(newField, page, targetPage).then((el)=>{
                    el.dataset.id = id;
                    newField.el = el;
                    if (!this.pdfFields[targetPage]) this.pdfFields[targetPage] = {};
                    this.pdfFields[targetPage][id] = newField;
                    this.enableCustom(newField);
                    this.refreshpdfFields();
                    this.saveChanges();
                })

            } else if (e.dataTransfer.getData("page") && e.dataTransfer.getData("id")) {
                const initialPage = Number(e.dataTransfer.getData("page"));
                const id = Number(e.dataTransfer.getData("id"));
                const pdfField = this.pdfFields[initialPage][id];
                const pdfFieldEl = pdfField.el;
                const posX =
                    Math.round(
                        normalizePosition(
                            (e.pageX - left) / textLayer.clientWidth,
                            parseFloat(pdfField.el.style.width)/100
                        ) * 1000
                    ) / 1000;
                const posY =
                    Math.round(
                        normalizePosition(
                            (e.pageY - top) / textLayer.clientHeight,
                            parseFloat(pdfField.el.style.height)/100
                        ) * 1000
                    ) / 1000;

                if (initialPage !== targetPage) {
                    pdfField.data.props.fieldInfo.position.page = targetPage;
                    this.pdfFields[targetPage][id] = pdfField;
                    delete this.pdfFields[initialPage][id];
                    page.appendChild(pdfFieldEl.parentElement.removeChild(pdfFieldEl));
                }

                Object.assign(pdfField.data.props.fieldInfo.position, {
                    posX,
                    posY,
                });

                Object.assign(pdfField.el.style, {
                    top: `${posY * 100}%`,
                    left: `${posX * 100}%`,
                    visibility: "visible",
                });
                this.saveChanges();
            } else {
                return;
            }
        }


        newId(page) {
            const ids = Object.keys(this.pdfFields[page] || ['0']);
            return parseInt(Math.max.apply(null, ids) ) + 1;
        }

        /**
         * Enables resizing and drag/drop for field items
         * @param {pdfField} pdfField
         */
        enableCustom(pdfField) {
            super.enableCustom(pdfField);
            if (pdfField.data.ispdfFieldEditable) {
                startResize(pdfField, this.onResizeItem.bind(this));
                this.registerDragEventsForpdfField(pdfField);
            }
        }

        // openDialogAfterInitialDrop(data) {
        //     this.dialog.add(InitialsAllPagesDialog, {
        //         addInitial: (role, targetAllPages) => {
        //             data.responsible = role;
        //             this.currentRole = role;
        //             this.addInitialpdfField(data, targetAllPages);
        //         },
        //         responsible: this.currentRole,
        //         roles: this.fieldRolesById,
        //     });
        // }

        /**
         * Inserts initial field items in the page
         * @param {Object} data data of the field item to be added
         * @param {Boolean} targetAllPages if the item should be added in all pages or only at the current one
         */
        addInitialpdfField(data, targetAllPages = false) {
            if (targetAllPages) {
                for (let page = 1; page <= this.pageCount; page++) {
                    const hassignatureItemsAtPage = Object.values(this.pdfFields[page]).some(
                        ({ data }) => data.type === "signature"
                    );
                    if (!hassignatureItemsAtPage) {
                        const id = generateRandomId();
                        const pdfFieldData = { ...data, ...{ page, id } };
                        this.renderpdfField(pdfFieldData, this.getPageContainer(page), id).then((el)=>{
                            this.pdfFields[page][id] = {
                                data: pdfFieldData,
                                el: el,
                            };
                        })
                     }
                }
            } else {
                this.renderpdfField(data, this.getPageContainer(data.page), date.id).then((el)=>{
                    this.pdfFields[data.page][data.id] = {
                        data,
                        el: el,
                    };
                })
            }
            this.saveChanges();
        }

        saveChanges() {}

        registerDragEventsForpdfField(pdfField) {
            const handle = pdfField.el.querySelector(".o_sign_config_handle");
            handle.setAttribute("draggable", true);
            handle.addEventListener("dragstart", (e) => this.onDragStart(e));
            handle.addEventListener("dragend", (e) => this.onDragEnd(e));
        }

        /**
         * Deletes a field item from the template
         * @param {pdfField} pdfField
         */
        deletepdfField(pdfField) {
            const { page } = pdfField.data.props.fieldInfo.position;
            const id = pdfField.el.dataset.id;
            pdfField.el.parentElement.removeChild(pdfField.el);
            delete this.pdfFields[page][id];
            this.saveChanges();
        }
    };
