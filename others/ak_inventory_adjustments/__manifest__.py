# -*- coding: utf-8 -*-
# Part of Odoo, Aktiv Software PVT. LTD.
# See LICENSE file for full copyright & licensing details.

# Author: Aktiv Software.
# mail: odoo@aktivsoftware.com
# Copyright (C) 2015-Present Aktiv Software PVT. LTD.
# Contributions:
#           Aktiv Software:
#              - Heli Kantawala
#              - Bhumi Zinzuvadiya
#              - Helly kapatel

{
    "name": "Inventory Adjustments",
    "category": "Inventory/Inventory",
    "summary": """Custom Inventory Adjustments""",
    "version": "18.0.0.0.02",
    "website": "http://www.aktivsoftware.com",
    "author": "Aktiv Software",
    "description": """Custom Inventory Adjustments for multi products""",
    "license": "AGPL-3",
    "depends": ["stock_account"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        'data/ir_sequence_data.xml',
        "views/stock_quant_views.xml",
        "views/stock_inventory_views.xml",
        "views/stock_inventory_line_views.xml",
        "report/stock_report_views.xml",
        "report/stock_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # "/ak_inventory_adjustments/static/src/xml/*.xml",
            # "/ak_inventory_adjustments/static/src/js/*.js",
        ]
    },
    "images": ["static/description/banner.jpg"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
