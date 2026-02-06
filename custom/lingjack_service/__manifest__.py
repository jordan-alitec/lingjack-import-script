# -*- coding: utf-8 -*-

{
    'name': "Lingjack Service",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',

    'version': '18.0.0.0.17',
    'description': """
Customisation for   
==================================================
    base for customising lingjack Service\n
    """,
    'depends': ['account', 'industry_fsm', 'sale', 'stock', 'industry_fsm_sale', 'sales_team', 'web', 'sale_tier_validation', 'ac_invoice_from_delivery'],
    'external_dependencies': {
        'python': ['qrcode', 'Pillow'],
    },
    'data': [
        'security/lingjack_control_tag_groups.xml',
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_line_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_location.xml',
        'views/qr_generation_wizard_views.xml',
        'views/menu_views.xml',
        'views/product.xml',
        'views/control_tag_views.xml',
        'views/account_move_views.xml',
        'wizards/change_unit_price_wizard_views.xml',
        'wizards/control_tag_report_wizard_views.xml',
        'reports/service_qr_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lingjack_service/static/src/components/product_catalog/kanban_model.js',
            'lingjack_service/static/src/components/product_catalog/kanban_record.js',
            'lingjack_service/static/src/components/product_catalog/kanban_view.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
