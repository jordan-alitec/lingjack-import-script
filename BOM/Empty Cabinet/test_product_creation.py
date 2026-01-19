#!/usr/bin/env python3
"""
Test script to diagnose product creation issues
"""

import xmlrpc.client
import sys

try:
    import config
    ODOO_URL = getattr(config, 'ODOO_URL', 'http://localhost:8069')
    ODOO_DB = getattr(config, 'ODOO_DB', 'your_database_name')
    ODOO_USERNAME = getattr(config, 'ODOO_USERNAME', 'admin')
    ODOO_PASSWORD = getattr(config, 'ODOO_PASSWORD', 'admin')
except ImportError:
    print("Error: config.py not found. Please create it from config_example.py")
    sys.exit(1)

# Connect to Odoo
common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})

if not uid:
    print("Authentication failed!")
    sys.exit(1)

models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

print("✓ Connected to Odoo")
print(f"User ID: {uid}\n")

# Test 1: Check product category
print("Test 1: Finding product category...")
try:
    categ_ids = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'product.category',
        'search',
        [[('name', '=', 'All')]],
        {'limit': 1}
    )
    if categ_ids:
        print(f"  ✓ Found category 'All' with ID: {categ_ids[0]}")
        categ_id = categ_ids[0]
    else:
        categ_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'product.category',
            'search',
            [[]],
            {'limit': 1}
        )
        if categ_ids:
            print(f"  ✓ Found category with ID: {categ_ids[0]}")
            categ_id = categ_ids[0]
        else:
            print("  ✗ No categories found")
            categ_id = False
except Exception as e:
    print(f"  ✗ Error: {e}")
    categ_id = False

# Test 2: Check UOM
print("\nTest 2: Finding UOM...")
try:
    uom_ids = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'uom.uom',
        'search',
        [[('name', '=', 'Units')]],
        {'limit': 1}
    )
    if uom_ids:
        print(f"  ✓ Found UOM 'Units' with ID: {uom_ids[0]}")
        uom_id = uom_ids[0]
    else:
        uom_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'uom.uom',
            'search',
            [[]],
            {'limit': 1}
        )
        if uom_ids:
            print(f"  ✓ Found UOM with ID: {uom_ids[0]}")
            uom_id = uom_ids[0]
        else:
            print("  ✗ No UOMs found")
            uom_id = False
except Exception as e:
    print(f"  ✗ Error: {e}")
    uom_id = False

# Test 3: Try to create a simple product
print("\nTest 3: Creating test product...")
test_reference = "TEST_PRODUCT_001"
test_name = "Test Product"

# Check if product already exists
existing = models.execute_kw(
    ODOO_DB, uid, ODOO_PASSWORD,
    'product.product',
    'search',
    [[('default_code', '=', test_reference)]],
    {'limit': 1}
)

if existing:
    print(f"  ⚠ Test product already exists with ID: {existing[0]}")
    print("  Deleting it first...")
    models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'product.template',
        'unlink',
        [[existing[0]]]
    )

product_vals = {
    'name': test_name,
    'default_code': test_reference,
    'type': 'product',
}

if categ_id:
    product_vals['categ_id'] = categ_id
    print(f"  Using category ID: {categ_id}")

if uom_id:
    product_vals['uom_id'] = uom_id
    product_vals['uom_po_id'] = uom_id
    print(f"  Using UOM ID: {uom_id}")

print(f"  Product values: {product_vals}")

try:
    template_id = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'product.template',
        'create',
        [product_vals]
    )
    print(f"  ✓ Created product template with ID: {template_id}")
    
    # Get product variant
    product_ids = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'product.product',
        'search',
        [[('product_tmpl_id', '=', template_id)]],
        {'limit': 1}
    )
    
    if product_ids:
        print(f"  ✓ Created product variant with ID: {product_ids[0]}")
        print("\n✓ Product creation test PASSED!")
    else:
        print("  ✗ Product variant not found")
        
except xmlrpc.client.Fault as e:
    print(f"  ✗ Odoo Fault Error: {e}")
    print(f"  Fault Code: {e.faultCode}")
    print(f"  Fault String: {e.faultString}")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test completed")










