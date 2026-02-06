# -*- coding: utf-8 -*-

{
    'name': "Lingjack BOM Extension",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',

    'version': '18.0.0.0.2',
    'description': """
BOM Extension for Lingjack
==================================================
    Extend MRP BOM with additional fields and webhook functionality\n
    - Area ID
    - SID Prefix
    - Node Type ID
    - Product search webhook
    - Route field for BOM lines (Buy/Make/Buy/Make)
    - Stock route manufacturing identification
    """,
    'depends': ['base', 'mrp', 'product', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        # 'data/stock_route_data.xml',
        'views/mrp_bom_view.xml',
        'views/stock_route_view.xml',
        'wizards/change_bom_component_wizard.xml',
        'wizards/duplicate_bom_wizard.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}