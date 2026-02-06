"""
Configuration file for Odoo BoM Import
Copy this file to config.py and update with your Odoo credentials
"""

# Odoo Connection Settings
ODOO_URL = 'https://lingjack-data-migration-script-27889585.dev.odoo.com'  # Your Odoo server URL
ODOO_DB = 'lingjack-data-migration-script-27889585'            # Your Odoo database name
ODOO_USERNAME = 'DataMigration1'              # Your Odoo username
ODOO_PASSWORD = 'Alitec!@#456789'              # Your Odoo password

EXCEL_FILE = 'output.xlsx'    # Path to Excel file
DRY_RUN = False                       # Set to False to actually import

# Optional: Column mapping (if your Excel structure differs)
COLUMN_MAPPING = {
    'product_name': 0,      # Column index (0-based) for product name
    'reference': 4,          # Column index for product reference code
    'component_ref': 5,      # Column index for component reference
    'quantity': 6,           # Column index for quantity
    'uom': 7,               # Column index for unit of measure
}
