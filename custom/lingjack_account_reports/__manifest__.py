{
    'name': 'Lingjack Account Reports',
    'version': '18.0.1.0.2',
    'category': 'Accounting',
    'summary': 'Custom Account Reports with Additional Fields',
    'description': """
        Adds new fields to Aged Payable and Aged Receivable reports
    """,
    'author': 'Alitec',
    'depends': ['account_reports'],
    'data': [
        'data/account_reports_views.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "lingjack_account_reports/static/src/js/filters.js",
            "lingjack_account_reports/static/src/xml/filter_extra_options.xml",
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}