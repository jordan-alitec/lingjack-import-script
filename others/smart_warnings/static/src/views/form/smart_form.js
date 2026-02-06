/** @odoo-module */

import { parseXML } from "@web/core/utils/xml";
import { FormCompiler } from "@web/views/form/form_compiler";
import { FormRenderer } from "@web/views/form/form_renderer";
import { markup } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";


patch(FormRenderer.prototype, {
    /*
    * Re-write to trigger props.smartWarnings calculation and refresh
    */
    setup() {
        super.setup();
        this.state = useState({ smartWarnings: undefined });
        this.orm = useService("orm");
        onWillStart(async () => { await this._onRenderSmartAlerts(this.props) });
        onWillUpdateProps(async (nextProps) => { await this._onRenderSmartAlerts(nextProps) });
    },
    /*
    * The method to get topical smart alerts and rerender the component
    */
    async _onRenderSmartAlerts(props) {
        const resId = props.record.resId;
        const resModel = props.record.resModel;
        var smartAlerts = [];
        if (resId && resModel && resModel !== "smart.warning") {
            smartAlerts = await this.orm.call(
                "smart.warning", "action_return_warnings", [resModel, resId],
            );
        };
        if (smartAlerts.length > 0) {
            smartAlerts.forEach(alert => {
                alert.name = markup(alert.name);
                alert.description = markup(alert.description);
            });
        }
        else {
            smartAlerts = undefined
        };
        Object.assign(this.state, { smartAlerts: smartAlerts });
    },
});

patch(FormCompiler.prototype, {
    /*
    * Re-write to locate smart alerts DOM element
    * We have to use such an idiotic way instead of creating a container to avoid inehritance issues.
    * Regretfully, this is how Odoo owl works
    * For example, accountMoveRender will lack a component dependence then
    */
    compileForm(el, params) {
        const form = super.compileForm(el, params);
        const statusBar = form.querySelector(".o_form_statusbar");
        const template = `<t t-if="__comp__.state.smartAlerts">
            <t t-foreach="__comp__.state.smartAlerts" t-as="smartWarning" t-key="smartWarning.id">
                <div t-attf-class="alert alert-#{smartWarning.css_class} smart_alert" role="alertdialog">
                    <div role="alertdialog">
                        <strong><t t-out="smartWarning.name"/></strong> <t t-out="smartWarning.description"/>
                    </div>
                </div>
            </t>
        </t>`;
        const SmartAlertsWrapper = parseXML(template);
        if (statusBar) {
            statusBar.parentElement.insertBefore(SmartAlertsWrapper, statusBar.nextSibling);
        } else if (form.querySelector(".o_form_sheet_bg")) {
            form.querySelector(".o_form_sheet_bg").prepend(SmartAlertsWrapper);
        } else {
            form.prepend(SmartAlertsWrapper);
        };
        return form
    },
});
