# -*- coding: utf-8 -*-

{
    'name': "Inline Barcode Scanner Widget",
    'version': '18.0.1.0.0',
    'depends': ['web','yc_code_scanner_mobile'],
    'author': "Alitec Pte Ltd",
    'category': "Tools",
    'summary': 'Inline barcode/QR code scanner widget for Char fields with integrated scan button',
    'description': """
        Inline Barcode Scanner Widget
        ==============================
        
        This module provides an inline barcode/QR code scanner widget for Char fields.
        The widget displays a small scan button directly inside the input field for easy access.
        
        Features:
        - Inline scan button integrated into the input field
        - Supports both barcode and QR code scanning
        - Uses mobile camera and webcam
        - Clean and compact UI design
        
        Usage:
        ------
        Add widget="inline_barcode_scanner" to any Char field in your form view:
        
        <field name="barcode" widget="inline_barcode_scanner"/>
        
        Last Update: 2024
    """,
    'assets': {
        'web.assets_backend': [
            'inline_barcode_scanner/static/src/css/inline_barcode_scanner.css',
            ('include', 'web._assets_core'),
            # Include required libraries from yc_code_scanner_mobile
            'yc_code_scanner_mobile/static/src/libs/html5-qrcode.min.js',
            'yc_code_scanner_mobile/static/src/libs/quagga.min.js',
            # Our scanner components (self-contained, no cross-module imports)
            'inline_barcode_scanner/static/src/js/scanner_configurator.js',
            'inline_barcode_scanner/static/src/xml/scanner_configurator.xml',
            'inline_barcode_scanner/static/src/js/scanner_dialog.js',
            'inline_barcode_scanner/static/src/xml/scanner_dialog.xml',
            # Our widget files
            'inline_barcode_scanner/static/src/js/inline_barcode_scanner_widget.js',
            'inline_barcode_scanner/static/src/xml/inline_barcode_scanner_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

