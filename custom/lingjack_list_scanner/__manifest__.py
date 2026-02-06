# -*- coding: utf-8 -*-

{
    'name': "Lingjack List Scanner",
    'version': '18.0.1.0.2',
    'depends': ['web', 'yc_code_scanner_mobile'],
    'author': "Alitec Pte Ltd",
    'category': "Tools",
    'summary': 'Add Scan QR button to list views with js_class="list_scanner"',
    'description': """
        Lingjack List Scanner
        =====================
        
        This module adds a "Scan QR" button next to "Add a new line" button 
        in list views that have js_class="list_scanner" attribute.
        
        Features:
        - Generic module that works with any list view
        - Button appears next to "Add a new line" button
        - Only shows when js_class="list_scanner" is set on the list view
        
        Usage:
        ------
        Add js_class="list_scanner" to your list view:
        
        <list js_class="list_scanner">
            ...
        </list>
        
        Last Update: 2025
    """,
    'assets': {
        'web.assets_backend': [
            ('include', 'web._assets_core'),
            # Include required libraries from yc_code_scanner_mobile
            'yc_code_scanner_mobile/static/src/libs/html5-qrcode.min.js',
            'yc_code_scanner_mobile/static/src/libs/quagga.min.js',
            # Scanner components
            'lingjack_list_scanner/static/src/js/scanner_configurator.js',
            'lingjack_list_scanner/static/src/xml/scanner_configurator.xml',
            'lingjack_list_scanner/static/src/js/scanner_dialog.js',
            'lingjack_list_scanner/static/src/xml/scanner_dialog.xml',
            # Main module files
            'lingjack_list_scanner/static/src/js/list_scanner_button.js',
            'lingjack_list_scanner/static/src/xml/list_scanner_button.xml',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}


