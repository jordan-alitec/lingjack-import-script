/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { sortBy } from "@web/core/utils/arrays";
import { registry } from "@web/core/registry";
import { normalizePosition, startResize } from "./utils";

export class FieldsCustomPopover extends Component {
    static template = "pdfForm.fieldCustomPopover";

    setup() {
        this.alignmentOptions = [
            { title: _t("Left"), key: "left" },
            { title: _t("Center"), key: "center" },
            { title: _t("Right"), key: "right" },
        ];

        this.alignsOptions = [
            { title: _t("LeftAlign"), key: "left" },
            { title: _t("RightAlign"), key: "right" },
            { title: _t("TopAlign"), key: "up" },
            { title: _t("BottomAlign"), key: "down" },
        ];

        this.sizeOptions = [
            { title: _t("SameWidth"), key: "h" },
            { title: _t("SameHeight"), key: "v" },
            { title: _t("SameSize"), key: "alt" },
        ];

        this.state = useState({
            type: this.props.type,
            alignment: this.props.position.alignment,
            placeholder: this.props.placeholder,
            invisible: this.props.invisible,
            required: this.props.required,
            readonly: this.props.readonly,
            option_ids: this.props.option_ids,
            position: this.props.position,
            // options: JSON.stringify(this.props.options),
            domain: this.props.domain,
            context: this.props.context,
            widget: this.props.widget,
            widgets: this.getWowlFieldWidgets(this.props.type, this.props.widget),
        });
        this.typesWithAlignment = new Set(["text", "textarea"]);
    }

    onChange(key, value) {
        this.state[key] = value;
        if (key === "alignment") this.state.position.alignment = value;
    }

    groupChange(key, value) {
        for (var i = 0; i < this.props.selection.length; i++) {
            switch (value) {
                case "left":
                    if (key === "alignment") {
                        Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                            alignment: value,
                        });
                    } else {
                        Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                            posX: this.props.selection[0].data.props.fieldInfo.position.posX,
                        });
                    }
                    break;
                case "center":
                    Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                        alignment: value,
                    });
                    break;
                case "up":
                    Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                        posY: this.props.selection[0].data.props.fieldInfo.position.posY,
                    });
                    break;
                case "v":
                    Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                        height: this.props.selection[0].data.props.fieldInfo.position.height,
                    });
                    break;
                case "h":
                    Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                        width: this.props.selection[0].data.props.fieldInfo.position.width,
                    });
                    break;
                case "alt":
                    Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                        height: this.props.selection[0].data.props.fieldInfo.position.height,
                        width: this.props.selection[0].data.props.fieldInfo.position.width,
                    });
                    break;
                case "down":
                    Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                        posY: this.props.selection[i].data.props.fieldInfo.position.posY +
                            this.props.selection[i].data.props.fieldInfo.position.height -
                            this.props.selection[0].data.props.fieldInfo.position.height,
                    });
                    break;
                case "right":
                    if (key === "alignment") {
                        Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                            alignment: value,
                        });
                    } else {
                        Object.assign(this.props.selection[i].data.props.fieldInfo.position, {
                            posX: this.props.selection[i].data.props.fieldInfo.position.posX -
                                this.props.selection[i].data.props.fieldInfo.position.width +
                                this.props.selection[0].data.props.fieldInfo.position.width,
                        });
                    }
                    break;
            }
            var options = this.props.selection[i].data.props.fieldInfo.position;
            const normalizedPosX =
                Math.round(normalizePosition(options.posX, options.width) * 1000) / 1000;
            const normalizedPosY =
                Math.round(normalizePosition(options.posY, options.height) * 1000) / 1000;
            Object.assign(this.props.selection[i].el.style, {
                top: `${normalizedPosY * 100}%`,
                left: `${normalizedPosX * 100}%`,
                width: `${options.width * 100}%`,
                height: `${options.height * 100}%`,
                "text-align": `${options.alignment}`,
            });
        }
        this.props.saveChanges(true);
    }

    parseInteger(value) {
        return parseInt(value);
    }

    onValidate() {
        this.props.onValidate(this.state);
    }

    get showAlignment() {
        return this.typesWithAlignment.has(this.props.type);
    }

    getWowlFieldWidgets(
        fieldType,
        currentKey = "",
        blacklistedKeys = [],
        debug = false
    ) {
        const wowlFieldRegistry = registry.category("fields");
        const widgets = [];
        for (const [widgetKey, Component] of wowlFieldRegistry.getEntries()) {
            if (widgetKey !== currentKey) {
                // always show the current widget
                // Widget dosn't explicitly supports the field's type
                if (!Component.supportedTypes || !Component.supportedTypes.includes(fieldType)) {
                    continue;
                }
                // Widget is view-specific or is blacklisted
                if (widgetKey.includes(".") || blacklistedKeys.includes(widgetKey)) {
                    continue;
                }
            }
            widgets.push([widgetKey, Component.displayName]);
        }
        return sortBy(widgets, (el) => el[1] || el[0]);
    }

}
