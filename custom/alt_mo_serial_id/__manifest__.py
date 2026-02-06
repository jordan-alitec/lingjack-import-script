# -*- coding: utf-8 -*-
{
    'name': 'Production Serial Registry (Alt MO Serial ID)',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Unit registry (Service ID) per manufactured unit, auto-generated on MO done',
    'description': """
Production Serial Registry
==========================
- Unique Service ID per manufactured unit (category prefix + company-wide sequence)
- Auto-create production.serial records when MO is marked done
- PWO number, Com No, MFG period, location
- Ready for future move-line and Setsco linking (via lingjack_alt_mo_serial_id)
    """,
    'author': 'Alitec',
    'website': 'https://www.alitec.sg',
    'depends': ['base', 'mrp', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/product_template_views.xml',
        'views/production_serial_views.xml',
        'views/mrp_production_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
