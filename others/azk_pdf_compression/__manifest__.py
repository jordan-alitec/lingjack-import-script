# -*- coding: utf-8 -*-
{
    'name': "PDF Attachment Compression",
    
    'summary': """Compress PDF Attachments based on model, size and age in addition to select the output quality""",

    'description': """
        This module includes:
        - A rules model to specify the attachment compression rules
        - A scheduled action to run the active compression rules
        - Option to run individual rules from server actions
    """,
    
    'author': "Azkatech",
    'website': "http://azka.tech",
    "license": "AGPL-3",
    "support": "support+apps@azka.tech",
    "price": 30.00,
    "currency": "USD",
    'category': 'Tools',
    'version': '18.0.0.0',
    'application': False,
    
    'depends': ['base','mail'],

    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/compression_rules_view.xml',
        'wizard/debug_rule.xml',
    ],
    'images': ['static/description/banner.png'],
}
