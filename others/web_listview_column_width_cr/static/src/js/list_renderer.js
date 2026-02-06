/** @odoo-module **/
import {ListRenderer} from "@web/views/list/list_renderer";
import {browser} from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { useMagicColumnWidths } from "./hooks/column_width_hook";


patch(ListRenderer.prototype, {

    setup() {
        super.setup();
        this.columnWidths = useMagicColumnWidths(this.tableRef, () => {
            return {
                columns: this.columns,
                isEmpty: !this.props.list.records.length || this.props.list.model.useSampleModel,
                hasSelectors: this.hasSelectors,
                hasOpenFormViewColumn: this.hasOpenFormViewColumn,
                hasActionsColumn: this.hasActionsColumn,
                self: this,
            };
        });
    },

});