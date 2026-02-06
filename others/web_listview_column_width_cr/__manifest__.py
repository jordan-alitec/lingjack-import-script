
{
    'name': 'List View Column width Adjustment',
    'version': '18.0.1.0',
    'summary': 'List View Column width Adjustment',
    'author': 'Candidroot Solutions Pvt. Ltd.',
    'description': """
			This module allows user to adjustment of any list view column width.
    """,
    'depends': ['web'],
    'category': 'Extra Tools',
    'demo': [
    ],
    'assets': {
        'web.assets_backend': [
            '/web_listview_column_width_cr/static/src/js/hooks/column_width_hook.js',
            '/web_listview_column_width_cr/static/src/js/list_renderer.js',
            '/web_listview_column_width_cr/static/src/scss/main.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
