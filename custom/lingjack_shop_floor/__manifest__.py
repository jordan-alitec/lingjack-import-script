# -*- coding: utf-8 -*-

{
    'name': "LingJack Shop Floor",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Manufacturing',
    'version': '18.0.0.0.6',
    'summary': 'Shop Floor Employee Time Tracking and Quantity Production',
    'description': """
        LingJack Shop Floor Module
        ==========================
        
        This module provides shop floor functionality for employees to:
        - Track start and stop times for work sessions
        - Log quantity produced during work sessions
        - Pop-up forms for easy data entry
        - Integration with manufacturing work orders
        - Shop floor optimized interface
        
        Features:
        - Employee work session management
        - Quantity produced tracking with pop-up forms
        - Integration with MRP work orders
        - Touch-friendly interface for shop floor use
        - Real-time production monitoring
    """,
    'depends': [
        'base',
        'hr',
        'mail',
        'mrp',
        'mrp_workorder',
        'lingjack_operation',
        'purchase_requisition',
    ],
    'data': [
        # Security
        'security/shop_floor_security.xml',
        'security/ir.model.access.csv',
        # Views
        'views/mrp_workorder.xml',
        'views/mrp_production.xml',
        'views/product.xml',
        'views/stock_picking.xml',
        'views/mrp_routing_views.xml',
        'views/mrp_operation_template.xml',
        'views/res_config_settings_views.xml',
        'views/mrp_workcenter_productivity_gantt_views.xml',
        'views/stock_move_lot_selection.xml',
        # Wizard views
        'wizards/shop_floor_quantities_pop_up.xml',
        'wizards/shop_floor_pick_components.xml',
        'wizards/mrp_purchase_request_wizard.xml',
        'wizards/lot_selection_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lingjack_shop_floor/static/src/css/shop_floor.css',
            'lingjack_shop_floor/static/src/js/shop_floor_widget.js',
            # MRP display
            'lingjack_shop_floor/static/src/mrp_display/mrp_display_action.js',
            'lingjack_shop_floor/static/src/mrp_display/mrp_display_record.js',
            'lingjack_shop_floor/static/src/mrp_display/mrp_display_record.scss',
            'lingjack_shop_floor/static/src/mrp_display/mrp_display_record.xml',
            'lingjack_shop_floor/static/src/mrp_display/dialog/mrp_menu_dialog.xml',
            'lingjack_shop_floor/static/src/mrp_display/dialog/mrp_menu_dialog.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
} 