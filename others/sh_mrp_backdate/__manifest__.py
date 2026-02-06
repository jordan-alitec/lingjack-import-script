# -*- coding: utf-8 -*-
# Part of Softhealer Technologies

{
    "name": "MRP Backdate | Manufacturing Backdate",
    "author" : "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "summary": "Backdate Backdate for MRP module",
    "description": """OThis selected date and remarks are also reflects in the stock moves, product moves & journal entries.""",
    "version": "0.0.6",
    "depends": ["stock", "stock_account", "mrp", "account"],
    "data": [
        'security/ir.model.access.csv',
        'security/sh_mrp_backdate_groups.xml',
        'wizard/mrp_backdate_wizard_views.xml',
        'views/mrp_config_settings_views.xml',
        'views/mrp_production_views.xml',
        'views/stock_move_views.xml',
        'views/stock_move_line_views.xml',
        'data/mrp_production_data.xml',
    ],

    "auto_install": False,
    "installable": True,
    "application": True,
    "images": ["static/description/background.gif",],
    "license": "OPL-1",
    "price": 114.66,
    "currency": "EUR"
}
