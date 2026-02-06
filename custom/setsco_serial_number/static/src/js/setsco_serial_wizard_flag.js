/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { onWillUnmount } from "@odoo/owl"; 

patch(FormController.prototype,{
    setup() {
        window.customScannerActive = false;
        if (this.props.resModel === "setsco.serial.selection.wizard") {
            window.customScannerActive = true;
            onWillUnmount(() => {
                window.customScannerActive = false;
                
            });
        }
        return super.setup(...arguments);
    },
});

