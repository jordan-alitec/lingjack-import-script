{
    'name': "Setsco Serial Number",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',
    'version': '18.0.0.0.14',

    'description': """
Setsco Serial Number Management
==================================================
    Custom serial number system for traceability and state management\n
    - Purchase setsco serial numbers from vendors
    - Link manufactured products to setsco serial numbers
    - Stock move integration with setsco serial number selection
    - State management: new, warehouse, delivered
    - Complete traceability system
    - Distribution record generation for fire extinguishers
    - Internal company transfer operations with reverse functionality
    """,
    'depends': ['base', 'purchase', 'stock_barcode', 'mrp', 'product', 'ac_invoice_from_delivery', 'lingjack_shop_floor', 'barcodes'],
    'data': [
        # Security
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/paper.xml',
        'data/report_data.xml',
        # Wizards
        'wizards/distribution_record_wizard.xml',
        'wizards/internal_company_transfer_wizard.xml',
        'wizards/internal_company_receive_wizard.xml',
        'wizards/setsco_serial_assignment_wizard.xml',
        'wizards/setsco_serial_range_wizard.xml',
        'wizards/setsco_serial_selection_wizard.xml',
        'wizards/mrp_selection_wizard.xml',
        # Views
        'views/product_view.xml',
        'views/setsco_category_views.xml',
        'views/setsco_serial_number_view.xml',
        'views/stock_view.xml',
        'views/mrp_view.xml',
        'views/distribution_settings_view.xml',
        'views/res_config_settings_views.xml',
        'views/menu_view.xml',

           ],
    'assets': {
        'web.assets_backend': [
            'setsco_serial_number/static/src/js/barcode_control_service.js',
            'setsco_serial_number/static/src/js/barcode_picking_model_patch.js',
            'setsco_serial_number/static/src/js/custom_qr_scan.js',
            'setsco_serial_number/static/src/xml/barcode_move_line.xml',
            'setsco_serial_number/static/src/js/barcode_move_line.js',
            'setsco_serial_number/static/src/js/setsco_serial_wizard_flag.js',
            'setsco_serial_number/static/src/css/setsco_serial_wizard.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True
} 