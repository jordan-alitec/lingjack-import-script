# -*- coding: utf-8 -*-

{
    'name': "lingjack_operation",
    'author': "Alitec Pte Ltd",
    'website': "http://www.alitec.sg",
    'category': 'Alitec',

    'version': '18.0.0.1.94',
    'description': """
Customisation for 
==================================================
    base for customising Operation\n
    - Last Update: 05-FEB-2026
    """,
    'depends': ['base','sale_timesheet','sale','stock','hr','purchase','quality','project_stock','account_asset','purchase_requisition'],
    'data': [
        'data/ir_sequence_data.xml',
        'data/purchase_sequence_data.xml',
        'data/ir_cron_auto_close_pr.xml',
        'security/security.xml',
        'security/ir_rule.xml',
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/stock_view.xml',
        'views/sale_view.xml',
        'views/account_view.xml',
        'views/product_view.xml',
        'views/crm_view.xml',
        'views/mrp.xml',
        'views/customer_part_number_view.xml',
        'views/quality_view.xml',
        'views/purchase_view.xml',
        'views/res_config_settings_view.xml',
        'views/product_supplierinfo_views.xml',
        'views/res_bank_views.xml',
        'views/account_payment_views.xml',
        'views/res_partner_bank_views.xml',
        'wizard/edit_product_template_wizard.xml',
        'views/uom_uom_views.xml',
        'wizard/confirm_export_control_wizard.xml',
        'wizard/stock_signature_wizard_view.xml',
        'wizard/driver_incomplete_wizard_view.xml',
        'wizard/account_payment_register_view_inherit.xml',
        'wizard/stock_picking_attachment_wizard.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
