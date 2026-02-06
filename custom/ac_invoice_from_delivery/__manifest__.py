# -*- coding: utf-8 -*-
{
    'name': "Create Sales Invoice From Delivery Orders",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',
    'version': '18.0.0.0.10',
    'description': """
    - Last Update: 05-feb-2026
    """,
    'depends': ['sale', 'stock', 'sale_stock', 'account','repair'],
    'data': [
        'security/ir.model.access.csv',
        'views/picking.xml',
        'views/server_action.xml',
        'views/account_move.xml',
        'wizards/wiz_confirm_unlink_picking_from_invoice.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
