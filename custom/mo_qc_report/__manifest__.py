# -*- coding: utf-8 -*-

{
    'name': "QC PDF Report",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',

        'version': '18.0.0.0.60',
    'description': """
    - Last Update: 10-JULY-2025
    """,
    'depends': ['base','lingjack_operation', 'mrp','web', 'quality_control', 'quality', 'quality_mrp_workorder'],
    'data': [
        'views/quality_view.xml',
        'reports/qc_report_header.xml',
        'reports/qc_report_template.xml',
        'reports/qc_report_action.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
