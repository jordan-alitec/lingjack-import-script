from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    return
    """Migrate setsco category data from product categories to products."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Get all product categories with setsco categories
    cr.execute("""
        SELECT id, setsco_category_id 
        FROM product_category 
        WHERE setsco_category_id IS NOT NULL
    """)
    category_mappings = cr.fetchall()

    # Update all products in those categories
    for category_id, setsco_category_id in category_mappings:
        if not setsco_category_id:
            continue

        # Update all products in this category
        cr.execute("""
            UPDATE product_template 
            SET setsco_category_id = %s
            WHERE categ_id = %s
        """, (setsco_category_id, category_id))

    # Drop the setsco_category_id column from product.category
    cr.execute("""
        ALTER TABLE product_category 
        DROP COLUMN IF EXISTS setsco_category_id
    """)

    # Update setsco.serial.number records to use product's setsco category
    cr.execute("""
        UPDATE setsco_serial_number ssn
        SET setsco_category_id = pt.setsco_category_id
        FROM product_product pp
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE ssn.product_id = pp.id
    """) 