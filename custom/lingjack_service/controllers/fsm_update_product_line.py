# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route
from odoo.addons.industry_fsm_sale.controllers.catalog import CatalogControllerFSM

class FSMCatalogControllerFSM(CatalogControllerFSM):

    @route()
    def product_catalog_update_order_line_info(self, res_model, order_id, product_id, quantity=0, **kwargs):
        """ Update sale order line information on a given sale order for a given product.

        :param int order_id: The sale order, as a `sale.order` id.
        :param int product_id: The product, as a `product.product` id.
        :param int task_id: The task, as a `project.task` id. also available in the context but clearer in argument
        :param float quantity: The quantity selected in the product catalog.
        :param list context: the context comming from the view, used only to propagate the 'fsm_task_id' for the action_assign_serial on the product.
        :return: The unit price of the product, based on the pricelist of the sale order and
                 the quantity selected.
        :rtype: A dictionary containing the SN action and the SOL price_unit
        """
        task_id = kwargs.get('task_id')
        if not task_id:
            return super().product_catalog_update_order_line_info(res_model, order_id, product_id, quantity, **kwargs)
        request.update_context(fsm_task_id=task_id)
        task = request.env['project.task'].browse(task_id)
        product = request.env['product.product'].browse(product_id)
        
        # Update task's current_special_id if special_id is provided in kwargs
        # This ensures _inverse_fsm_quantity can access it via task.current_special_id
        special_id = kwargs.get('special_id')
        if special_id and task:
            task.update_special_id(special_id)
        
        # Call set_fsm_quantity which triggers _inverse_fsm_quantity
        # _inverse_fsm_quantity reads from task.current_special_id
        SN_wizard = product.set_fsm_quantity(quantity)
        
        # Find the sale order line for this product and task
        # When filtering by special_id, we need to find the line for current month
        from datetime import date
        current_month = str(date.today().month)
        sol = request.env['sale.order.line'].search([
            ('order_id', '=', task.sale_order_id.id),
            ('product_id', '=', product_id),
            ('task_id', '=', task_id),
            ('fsm_month', '=', current_month),
        ], limit=1)
        
        # Get min_quantity if available (for minimumQuantityOnProduct prop)
        # min_quantity = product.minimum_quantity if hasattr(product, 'minimum_quantity') else False
        min_quantity = 0
        return {
            "action": SN_wizard,
            "price": sol.price_unit if sol else False,
            "min_quantity": min_quantity,
        }
