# -*- coding: utf-8 -*-

{
    'name': 'Odoo Freeze ListView Header',
    'version': '1.0',
    'category': 'All',
    'sequence': 6,
    'author': 'ErpMstar Solutions',
    'summary': 'Allows you to freeze listview header',
    'depends': ['web'],
    'data': [
        # 'security/ir.model.access.csv',
        # 'views/view.xml',
        # 'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            "odoo_list_freeze_header/static/src/css/web.css",
        ],
        'web.assets_qweb': [
            
        ],
    },
    'images': [
        'static/description/list.jpg',
    ],
    'installable': True,
    'website': '',
    'auto_install': False,
    'price': 9,
    'currency': 'EUR',
    'bootstrap': True,
}
