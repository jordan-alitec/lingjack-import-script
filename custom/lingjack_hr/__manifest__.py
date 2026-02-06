# -*- coding: utf-8 -*-

{
    'name': "Lingjack HR",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Human Resources',
    'version': '18.0.0.0.1',
    'description': """
Lingjack HR Customization
==================================================
This module extends the HR Employee model to make employee fields 
accessible to base.group_user (Internal Users).

The module updates field access groups for various HR employee fields 
including personal information, contact details, identification numbers, 
and other employee-related data to ensure they are accessible to 
internal users.
    """,
    'depends': ['hr', 'hr_attendance'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
