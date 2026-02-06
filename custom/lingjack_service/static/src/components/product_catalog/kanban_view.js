/** @odoo-module **/
import { registry } from "@web/core/registry";
import { LingjackServiceProductCatalogKanbanRecord } from "./kanban_record";
import { FSMProductCatalogKanbanController } from "@industry_fsm_sale/components/product_catalog/kanban_controller";
import { LingjackServiceProductCatalogKanbanModel } from "./kanban_model";
import { productCatalogKanbanView } from "@product/product_catalog/kanban_view";
import { ProductCatalogKanbanRenderer } from "@product/product_catalog/kanban_renderer";

export class LingjackServiceProductCatalogKanbanRenderer extends ProductCatalogKanbanRenderer {
    static components = {
        ...ProductCatalogKanbanRenderer.components,
        KanbanRecord: LingjackServiceProductCatalogKanbanRecord,
    };

    get createProductContext() {
        return { default_invoice_policy: "delivery" };
    }
}

export const lingjackServiceProductCatalogKanbanView = {
    ...productCatalogKanbanView,
    Renderer: LingjackServiceProductCatalogKanbanRenderer,
    Controller: FSMProductCatalogKanbanController,
    Model: LingjackServiceProductCatalogKanbanModel,
};

// Override the existing fsm_product_kanban view to use our custom model
// Remove the existing view first (if it exists), then add our custom one
try {
    registry.category("views").remove("fsm_product_kanban");
} catch (e) {
    // View might not exist yet, which is fine
}
registry.category("views").add("fsm_product_kanban", lingjackServiceProductCatalogKanbanView);

