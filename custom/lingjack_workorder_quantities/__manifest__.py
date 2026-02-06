{
    'name': 'Lingjack Workorder Quantities',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Enhanced workorder quantity handling for manufacturing backorders',
    'description': """
        This module enhances the handling of workorder quantities when creating manufacturing backorders.
        Features:
        - Properly tracks progress of each operation independently
        - Creates backorders with correct remaining quantities for each workorder
        - Considers both qualified and defect quantities when calculating remaining work
        - Ensures backorder quantity is based on actual progress of operations
    """,
    'author': 'Lingjack',
    'website': 'https://www.lingjack.com',
    'depends': [
        'mrp',
        'lingjack_shop_floor',
    ],
    'data': [
        'security/ir.model.access.csv',
        # Views
        'views/mrp_workorder.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 