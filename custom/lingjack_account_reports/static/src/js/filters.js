/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

patch(AccountReportFilters.prototype , {

    async toggleShowPaymentTerms() {
        await this.controller.toggleOption('show_payment_terms', true);
    },

    async toggleShowSalesTeam() {
        await this.controller.toggleOption('show_sales_team', true);
    },

    async toggleShowSalesPerson(){
        await this.controller.toggleOption('show_sales_person', true);
    }

})