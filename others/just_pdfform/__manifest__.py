# See LICENSE file for full copyright and licensing details.

{
    "name": "PDF Form and Report",
    "version": "1.0",
    "author": "justzxw",
    "complexity": "easy",
    "depends": ["web"],
    "license": "AGPL-3",
    "category": "Tools",
    "description": """
     This module provides the new pdf form view, user can fill a form with a PDF file as background.
    """,
    "summary": """
        Define a pdf view and drop fields in area, then user can fill a form with a PDF file as background.
    """,
    "images": ["static/description/Sale_order_report_define.png",
               "static/description/Sale_order_contract_sign.png",
               "static/description/HR_PDF_Form_PDF_edit.png",
               ],
    "depends": ["sale","hr"],
    "data": [
        "views/pdfformdemo.xml",
        "views/ir_ui_view.xml",
        ],

    "installable": True,
    "auto_install": False,
    'assets': {
        'web.assets_backend': [
            'web/static/lib/jquery/jquery.js',
            'web/static/src/legacy/js/libs/jquery.js',
            'just_pdfform/static/src/pdfform/*.js',
            'just_pdfform/static/src/xml/*.xml',
        ],
    },

    "price": 500.0,
    "currency": "USD",
}
