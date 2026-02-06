/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, onWillUnmount, useEffect, useRef, onMounted, onWillRender,useState, onWillStart  } from "@odoo/owl";
import { standardViewProps } from "@web/views/standard_view_props";
import { PdfFormTemplateBody } from "./pdfform_body";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { CogMenu } from "@web/search/cog_menu/cog_menu";
import { Layout } from "@web/search/layout";
import { Field } from "@web/views/fields/field";
import { FormController } from "@web/views/form/form_controller";
import { FormStatusIndicator } from "@web/views/form/form_status_indicator/form_status_indicator";
import { evaluateExpr, evaluateBooleanExpr } from "@web/core/py_js/py";
import { useService } from "@web/core/utils/hooks";

export class PdfFormController extends FormController {
    static template = 'pdfForm.Template';
    static components = {
        PdfFormTemplateBody, Layout, SearchBar, CogMenu, FormStatusIndicator,
    };

    setup() {
        this.props.resId = this.props.context.active_model === "ir.ui.view" ? false : this.props.context.active_id;
        super.setup();
		this.props.className = 'o_diagram_plus_view h-100';
        const params = this.props.modelParams;
        this.pdfTemplate = params.pdfTemplate;
        this.pdfTemplate.editor_view = false;
        this.pdfTemplate.xmlDoc = this.archInfo.xmlDoc;
        this.fields = params.fields;
        this.notification = useService("notification");

        onWillRender(async () => {
            var self = this;
            const record = this.model.root;
            this.props.record = record;
            var env = self.extendEnv(self.env, {model:self.model});
            this.pdfTemplate.activeActions.template = evaluateBooleanExpr(this.pdfTemplate.activeActions.template || '1', record.evalContextWithVirtualIds);
            this.childEnv = {env:env, models:this.props.relatedModels, resModel:this.props.resModel};
            this.pdfFields = $.map(this.props.archInfo.fieldNodes,
                function (conn,key) {    
                    conn.position = evaluateExpr(conn.attrs.position || "{}");            
                    const fieldprops = {
                        id: key,
                        name: conn.name,
                        record: record,
                        field: conn.field,
                        fieldInfo: conn,
                    };

                    conn.readonly = evaluateBooleanExpr(conn.readonly || '0', record.evalContextWithVirtualIds);
                    fieldprops.readonly = !params.pdfTemplate.activeActions.edit || conn.readonly || (self.props.record && !self.props.record.isInEdition) || false;              
                    fieldprops.invisible = evaluateBooleanExpr(conn.attrs.invisible || '0', record.evalContextWithVirtualIds);
                    fieldprops.required = evaluateBooleanExpr(conn.attrs.required || '0', record.evalContextWithVirtualIds);

                    if (fieldprops.readonly) {
                        fieldprops.fieldInfo.options.no_open = true;
                    }

                    var newField = new Field(fieldprops, env, self);
                    newField.field = conn.field;
                    return newField;
                }
            );

            if (self.props.context.active_model === "ir.ui.view") {
                self.pdfTemplate.editor_view = true;
                self.canCreate = false;
                self.canEdit = false   ;
                self.beforeVisibilityChange = function() {};
            }
            
            return Promise.all([this.fetchTemplateData()]);
        });
    }

    extendEnv(currentEnv, extension) {
        const env = Object.create(currentEnv);
        const descrs = Object.getOwnPropertyDescriptors(extension);
        return Object.freeze(Object.defineProperties(env, descrs));
    }

    async fetchTemplateData() {
        if (this.pdfTemplate.id == undefined) {
            this.notification.add(_t("The template doesn't exist anymore."), {
                title: _t("Warning"),
                type: "warning",
            });
            return;
        }
        this.attachmentLocation = `/web/content/${this.pdfTemplate.id}`;

        return Promise.all([
            this.fetchAttachment(),
        ]);
    }

    async fetchAttachment() {
        const attachment = await this.orm.call(
            "ir.attachment",
            "read",
            [[this.pdfTemplate.id], ["mimetype", "name"]],
            { context: this.props.context }
        );

        this.templateAttachment = attachment[0];
        this.PdfFormTemplate = attachment[0];
        this.pdfTemplate.hasTemplate = attachment.length > 0;
        //this.isPDF = this.templateAttachment.mimetype.indexOf("pdf") > -1;
    }

};

//PdfFormController.template = 'PdfFormView.buttons';
PdfFormController.props = {
    ...standardViewProps,
    Model: Function,
    modelParams: Object,
    archInfo: Object,
}
