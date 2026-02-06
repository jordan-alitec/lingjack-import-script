###############################################################################
# Copyright (C) 2025 Alitec
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)
###############################################################################
{
    'name': 'Lingjack Quality QC Sheet',
    'version': '18.0.1.0.0',
    'summary': 'QC spreadsheet per procurement group with BoM templates and MO linkage',
    'description': 'Reuse a Quality spreadsheet per procurement group from BoM-linked templates, including backorders.',
    'author': 'Alitec',
    'website': 'https://alitec.sg',
    'license': 'LGPL-3',
    'category': 'Manufacturing/Quality',
    'depends': ['base', 'mail', 'mrp', 'stock', 'quality_control', 'mrp_workorder'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_views.xml',
        'views/quality_check.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lingjack_quality_qc_sheet/static/src/mrp_display/dialog/mrp_menu_dialog_inherit.xml',
            'lingjack_quality_qc_sheet/static/src/mrp_display/dialog/mrp_menu_dialog_patch.js',
        ],
    },
    'installable': True,
    'application': False,
}
