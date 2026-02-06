# -*- coding: utf-8 -*-
# Part of Softhealer Technologies

{
    "name": "Inventory Backdate",
    "author" : "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "summary": "This module is useful for done picking orders (incoming order / delivery order / internal transfer) and scrap orders with selected backdate. You can put a custom backdate and remarks in the picking & scrap orders. You can mass assign backdate in one click. When you mass assign a While you assign babackdate, it asks for remarks in the mass assign wizard. This selected date and remarks are also reflects in the stock moves & product moves.",
    "description": """This module is useful for done picking orders (incoming order / delivery order / internal transfer) and scrap orders with selected backdate. You can put a custom backdate and remarks in the picking & scrap orders. You can mass assign backdate in one click. When you mass assign a While you assign babackdate, it asks for remarks in the mass assign wizard. This selected date and remarks are also reflects in the stock moves & product moves.""",
    "version": "0.0.6",
    "depends": ["stock", "account", "stock_account", "sh_inventory_adjustment_backdate"],
    "data": [
        'security/ir.model.access.csv',
        'security/sh_stock_backdate_groups.xml',
        'data/stock_picking_data.xml',
        'data/stock_scrap_data.xml',
        'wizard/sh_picking_backdate_wizard_views.xml',
        'wizard/sh_scrap_backdate_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
        'views/stock_scrap_views.xml',
        'views/stock_move_line_views.xml',
    ],

    "auto_install": False,
    "installable": True,
    "application": True,
    "images": ["static/description/background.gif",],
    "license": "OPL-1",
    "price": 114.66,
    "currency": "EUR"
}
