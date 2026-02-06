# -*- coding: utf-8 -*-
# Part of Softhealer Technologies

{
    "name": "Inventory Adjustment Backdate",
    "author" : "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "summary": "This module helps you make changes to your inventory records with past dates. You can specify a custom date and add notes for the adjustment. These details will be recorded not only in the inventory adjustments but also in related records like stock moves, product moves, and stock valuation.",
    "description": """This module helps you make changes to your inventory records with past dates. You can specify a custom date and add notes for the adjustment. These details will be recorded not only in the inventory adjustments but also in related records like stock moves, product moves, and stock valuation.""",
    "version": "0.0.6",
    "depends": ["account", "stock", "stock_account"],
    "data": [
        # 'views/res_config_settings_views.xml',
        'views/stock_move_views.xml',
        'views/stock_quant_views.xml',
    ],

    "auto_install": False,
    "installable": True,
    "application": True,
    "images": ["static/description/background.gif",],
    "license": "OPL-1",
    "price": 114.66,
    "currency": "EUR"
}
