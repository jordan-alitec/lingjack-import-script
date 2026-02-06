/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PdfFormController } from "./pdfform_controller";
import { Model } from "@web/model/model";
import { _t } from "@web/core/l10n/translation";
import { FormArchParser } from "@web/views/form/form_arch_parser";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { evaluateExpr, evaluateBooleanExpr } from "@web/core/py_js/py";

export const PdfFormView = {
    display_name: _t('Pdf Form'),
    icon: 'fa-code-fork',
    multi_record: false,
    searchable: false,

    // Disable search
    withSearchPanel: false,
    withSearchBar: false,

    type: 'pdfForm',
    viewType: 'pdfForm',

    Controller: PdfFormController,
    Model: RelationalModel,

    props: (props, view, config) => {
        const { ArchParser } = view;
        const { arch, relatedModels, resModel, info, record} = props;
        const archInfo = new FormArchParser().parse(arch, relatedModels, resModel);
        
        const pdftemplate = arch.getElementsByTagName("pdfTemplate") ? arch.getElementsByTagName("pdfTemplate")[0]: undefined;
        const fields = archInfo.fieldNodes;
        archInfo.activeActions.template = arch.getAttribute('template');

        var modelParams = {
            pdfTemplate: {viewId:config.viewId, 
                id: pdftemplate ? parseInt(pdftemplate.getAttribute('pdfid')) : undefined, 
                name: pdftemplate ? pdftemplate.textContent || 'no PDF' : ' no PDF ', activeActions: archInfo.activeActions,},
            config: config,
            fields: props.fields,
        };

        return {
            ...props,
            Model: view.Model,
            archInfo,
            modelParams,
        };
    },
};

registry.category("views").add("pdfForm", PdfFormView);
