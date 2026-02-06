{
	'name': 'LJ Barcode Qty Demand',
	'version': '18.0.1.0.7',
	'summary': 'Override barcode qty demand and PWO QR code scanning for SFP transfers',
	'description': 'Adds actual_reserve_qty to stock.move.line and makes barcode app use it as reserved quantity (qtyDemand). Also enables PWO QR code scanning to open SFP transfer notes.',
	'author': 'Your Company',
	'license': 'LGPL-3',
	'category': 'Inventory/Barcode',
	'depends': ['stock_barcode', 'lingjack_shop_floor', 'lingjack_sale_workorder', 'stock'],
	'assets': {
		'web.assets_backend': [
			'lj_barcode_qty_demand/static/src/models/barcode_picking_model_patch.js',
			# 'lj_barcode_qty_demand/static/src/models/barcode_mrp_model_patch.js',
			'lj_barcode_qty_demand/static/src/component/main.xml',
			'lj_barcode_qty_demand/static/src/component/main.js',
			'lj_barcode_qty_demand/static/src/component/sacnner.js',
			'lj_barcode_qty_demand/static/src/component/scanner.xml',
		],
	},
    'data': [
        'security/ir.model.access.csv',
        'wizard/stock_location_selection.xml',
    ],
}
