/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

patch(BarcodePickingModel.prototype, {
	_getMoveLineData(id) {
		const smlData = super._getMoveLineData(id);
		try {
			const picking = this.cache?.getRecord && this.cache.getRecord('stock.picking', this.resId);
			const useActual = !!(picking && typeof picking.production_count === 'number' && picking.production_count > 0);
			if (useActual && smlData && Object.prototype.hasOwnProperty.call(smlData, 'actual_reserve_qty')) {
				if (typeof smlData.actual_reserve_qty === 'number') {
					smlData.reserved_uom_qty = smlData.actual_reserve_qty;
				}
			}
		} catch (error) {
			// Handle case where stock.picking doesn't exist in cache
			console.warn('Could not access stock.picking in cache:', error);
		}
		return smlData;
	},

	getQtyDemand(line) {
		try {
			const picking = this.cache?.getRecord && this.cache.getRecord('stock.picking', this.resId);
			const useActual = !!(picking && typeof picking.production_count === 'number' && picking.production_count > 0);
			if (useActual && line && typeof line.actual_reserve_qty === 'number') {
				return line.actual_reserve_qty || 0;
			}
		} catch (error) {
			// Handle case where stock.picking doesn't exist in cache
			console.warn('Could not access stock.picking in cache for getQtyDemand:', error);
		}
		return super.getQtyDemand(line);
	},
});
