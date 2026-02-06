"""
Central Configuration File for BOM Import Scripts

This file contains all configuration settings for import scripts in the BOM directory.
All import scripts should read from this central configuration file.

To use this config:
1. Update the Odoo connection settings below
2. Update script-specific settings as needed
3. All import scripts will automatically use these settings
"""

# ============================================================================
# ODOO CONNECTION SETTINGS (Common to all scripts)
# ============================================================================
# # Odoo Connection Settings
# ODOO_URL = 'https://lingjack-data-migration-script-27889585.dev.odoo.com'  # Your Odoo server URL
# ODOO_DB = 'lingjack-data-migration-script-27889585'            # Your Odoo database name
# ODOO_USERNAME = 'DataMigration1'              # Your Odoo username
# ODOO_PASSWORD = 'Alitec!@#456789'              # Your Odoo password
ODOO_URL = 'https://lingjack.odoo.com/'
ODOO_DB = 'alitecpteltd-lingjack-main-21976694'
ODOO_USERNAME = 'dataimport'
ODOO_PASSWORD = 'Admin@123456'
# ============================================================================
# OPERATION IMPORT SETTINGS
# ============================================================================

OPERATION_EXCEL_FILE = 'Book1.xlsx'  # Excel file with domain, work center, and template columns
OPERATION_SHEET_NAME = None  # None = use active sheet
OPERATION_DRY_RUN = False  # Set to False to actually import
OPERATION_RETRIEVE = False  # Set to True to only retrieve matching BOMs without creating records
OPERATION_CATEGORY_COL = 1  # Column A: Domain filter for product_id (1-based)
OPERATION_COL = 2  # Column B: Operation Name (1-based) - DEPRECATED, now using new format

# ============================================================================
# SWO (Sale Work Order) IMPORT SETTINGS
# ============================================================================

SWO_EXCEL_FILE = 'output.xlsx'
SWO_SHEET_NAME = 'Outstanding SWO Listing'
SWO_DRY_RUN = False  # Set to False to actually import

# ============================================================================
# MRP (Manufacturing) IMPORT SETTINGS
# ============================================================================

MRP_EXCEL_FILE = 'output.xlsx'
MRP_SHEET_NAME = None  # None = use active sheet, or specify like 'Manufacturing Order (mrp.produc'
MRP_DRY_RUN = False  # Set to False to actually import

# ============================================================================
# EMPLOYEE IMPORT SETTINGS
# ============================================================================

EMPLOYEE_EXCEL_FILE = 'employee.xlsx'
EMPLOYEE_DRY_RUN = False  # Set to False to actually import

# Mapping from internal field keys to Excel header text
# Update these if your Excel headers differ
EMPLOYEE_HEADER_MAPPING = {
    # Identification / core info
    'employee_code': None,                  # no dedicated code column
    'employee_name': 'Employee Name',
    'department_name': 'Department',
    'job_title': 'Job Position',
    'manager_code': None,
    'manager_name': 'Manager',

    # Work contacts
    'work_email': 'Work Email',
    'work_phone': 'Work Phone',

    # Private contacts & address
    'private_email': 'Private Email',
    'private_phone': 'Private Phone',
    'private_street': 'Private Street',
    'private_street2': 'Private Street2',
    'private_zip': 'Private Zip',
    'private_city': 'Private City',
    'private_country': 'Private Country',

    # Identity / personal data
    'nationality': 'Nationality',
    'identification_no': 'Identification No',
    'ssn_no': 'SSN No',
    'passport_no': 'Passport No',
    'gender': 'Gender',
    'birthday': 'Date of Birth',
    'place_of_birth': 'Place of Birth',
    'country_of_birth': 'Country of Birth',
    'study_field': 'Field of Study',
    'visa_no': 'Visa No',
    'visa_expire': 'Visa Expiration Date',
    'work_permit_no': 'Work Permit No',
    'work_permit_expiration': 'Work Permit Expiration Date',
    'marital_status': 'Marital Status',
    'children': 'Number of Children',

    # HR / cost / badge
    'hourly_cost': 'Hourly Cost',
    'badge_id': 'Badge ID',

    # Emergency contact
    'emergency_contact_name': 'Contact Name',
    'emergency_contact_phone': 'Contact Phone',
}

# ============================================================================
# BOM IMPORT SETTINGS (for Actual BoM and Empty Cabinet)
# ============================================================================

BOM_EXCEL_FILE = 'output.xlsx'
BOM_DRY_RUN = False  # Set to False to actually import

# Optional: Column mapping (if your Excel structure differs)
BOM_COLUMN_MAPPING = {
    'product_name': 0,      # Column index (0-based) for product name
    'reference': 4,          # Column index for product reference code
    'component_ref': 5,      # Column index for component reference
    'quantity': 6,           # Column index for quantity
    'uom': 7,               # Column index for unit of measure
}

# ============================================================================
# SETSCO SERIAL NUMBER IMPORT SETTINGS
# ============================================================================

SETSCO_EXCEL_FILE = 'Setsco_Combined.xlsx'
SETSCO_DRY_RUN = False  # Set to False to actually import
SETSCO_LIST_EXCEL_FILE = 'SetscoList.xlsx'  # For import_setsco_list_to_odoo.py
# Which sheets to import (run Office + Warehouse first, then Production later)
SETSCO_LIST_IMPORT_OFFICE = True
SETSCO_LIST_IMPORT_WAREHOUSE = True
SETSCO_LIST_IMPORT_PRODUCTION = False

