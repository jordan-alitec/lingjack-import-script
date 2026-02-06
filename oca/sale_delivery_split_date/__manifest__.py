# Copyright 2018 Alex Comba - Agile Business Group
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Sale Delivery Split Date",
    "version": "18.0.1.0.0",
    "summary": "Sale Deliveries split by date",
    "author": "Agile Business Group, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/sale-workflow",
    "depends": [
        "sale_order_line_date",
        "sale_procurement_group_by_line",
    ],
    "data": [
        "views/stock_picking.xml",
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
    "category": "Alitec - Sales",
}
