# -*- coding: utf-8 -*-

{
    'name': "LingJack Sale Work Orders",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Manufacturing',
    'version': '18.0.0.0.7',
    'summary': 'Sale Work Order Management for Manufacturing',
    'description': """
    
        LingJack Sale Work Order Module
        ==============================
        
        This module provides functionality to manage manufacturing work orders created from sales:
        
        Features:
        - Automatic work order creation from sales orders
        - Track manufacturing progress per sale order
        - Manage production quantities and status
        - Integration with MRP and Sales modules
        - Manufacturing demand planning
        - Production tracking and monitoring
        
        Key Benefits:
        - Better coordination between sales and production
        - Clear visibility of manufacturing requirements
        - Efficient production planning
        - Improved customer delivery tracking
    """,
    'depends': [
        'base',
        'sale',
        'sale_mrp',
        'mrp',
        'mrp_workorder',
        'lingjack_operation',
        'lingjack_bom_extension',
    ],
    'data': [
        # Security
        'security/sale_workorder_security.xml',
        'security/ir.model.access.csv',

        # Sequence
        'data/ir_sequence_data.xml',

        # Viewsp
        'views/sale_work_order_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_production_sfp_distribution_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
} 