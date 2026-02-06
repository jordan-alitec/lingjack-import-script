# -*- coding: utf-8 -*-
{
    'name': "Mo Priority Indicator",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',
    'version': '18.0.0.1',
    'description': """ Mo Priority Indicator """,
    'depends': ['base', 'mrp', 'mrp_workorder'],
    'data': [
        'views/mrp_production.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mo_priority_indicator/static/src/mrp_display/mrp_display.js',
            'mo_priority_indicator/static/src/mrp_display/mrp_display_action.js',
            'mo_priority_indicator/static/src/mrp_display/mrp_display_record.xml',
            'mo_priority_indicator/static/src/mrp_display/mrp_display_record.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
