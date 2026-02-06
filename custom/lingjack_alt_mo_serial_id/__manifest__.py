# -*- coding: utf-8 -*-
{
    'name': 'Lingjack Alt MO Serial ID (Setsco Link)',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Link production.serial with setsco.serial.number; auto-link on MO done',
    'description': """
Link Production Serial with Setsco
===================================
- Adds setsco_serial_id on production.serial
- Adds production_serial_id on setsco.serial.number
- One-to-one linking when MO is marked done (if product requires Setsco)
- Uniqueness: one Setsco cannot be mapped to multiple active production.serial
    """,
    'author': 'Alitec',
    'website': 'https://www.alitec.sg',
    'depends': ['alt_mo_serial_id', 'setsco_serial_number'],
    'data': [
        'views/production_serial_views.xml',
        'views/setsco_serial_number_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
