# -*- coding: utf-8 -*-

{
    'name': "LingJack Search Picking",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Inventory',
    'version': '18.0.0.0.5',
    'description': """
LingJack Search Picking
=======================
Search stock pickings by barcode scanning
    - Camera barcode scanner
    - Search by picking number
    - Search by previous transfer
    - Quick search and navigation
    - Last Update: 10-OCT-2025
    """,
    'depends': ['base', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/menu.xml',
        'wizards/picking_search_wizard.xml',
        'wizards/previous_transfer_search_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lingjack_search_picking/static/src/js/picking_scanner.js',
            'lingjack_search_picking/static/src/js/previous_transfer_scanner.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}

