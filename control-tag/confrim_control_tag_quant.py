#!/usr/bin/env python3
"""
Apply inventory adjustment (action_apply_inventory) for stock.quant records.

Replicates the "Apply" button (stock.action_stock_inventory_adjustement_name)
for a large number of quants (e.g. product_id=35808) in batches so Odoo does
not hang. Run from command line or adjust PRODUCT_ID / batch size as needed.

Usage:
  python confrim_control_tag_quant.py [--dry-run] [--product-id 35808] [--batch-size 100] [--reference "Import From IND4"]
  --dry-run     : Only search and report count, do not call action_apply_inventory.
  --product-id  : product.product id to filter quants (default: 35808).
  --batch-size  : Number of quant IDs per RPC call (default: 100).
  --reference   : inventory_name in context for stock moves (default: "Import From IND4").
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import xmlrpc.client

# Path setup: optional config from BOM parent
script_dir = Path(__file__).resolve().parent
bom_dir = script_dir.parent / "BOM"
if bom_dir.exists() and str(bom_dir) not in sys.path:
    sys.path.insert(0, str(bom_dir))

# Odoo connection (same pattern as control-tag.py; override via env or edit)
# ODOO_URL = os.environ.get('ODOO_URL', 'http://localhost:8069')
# ODOO_DB = os.environ.get('ODOO_DB', 'lingjack-test')
# ODOO_USERNAME = os.environ.get('ODOO_USERNAME', 'admin')
# ODOO_PASSWORD = os.environ.get('ODOO_PASSWORD', 'admin')

# ODOO_URL = 'https://lingjack.odoo.com/'
# ODOO_DB = 'alitecpteltd-lingjack-main-21976694'
# ODOO_USERNAME = 'dataimport'
# ODOO_PASSWORD = 'Admin@123456'

ODOO_URL = 'http://localhost:8099'
ODOO_DB = 'lingjack-test4'
ODOO_USERNAME = 'dataimport'
ODOO_PASSWORD = 'Admin@123456'

INVENTORY_ADJUSTMENT_REFERENCE = 'Import From IND4'
DEFAULT_PRODUCT_ID = 35808
DEFAULT_BATCH_SIZE = 100

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)
log_file_path = script_dir / 'confirm_control_tag_quant.log'
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(file_handler)


def get_connection(url: str):
    """Return (common, models) XML-RPC proxies."""
    common = xmlrpc.client.ServerProxy(f'{url.rstrip("/")}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{url.rstrip("/")}/xmlrpc/2/object')
    return common, models


def search_quants_to_apply(
    models,
    db: str,
    uid: int,
    password: str,
    product_id: int,
) -> List[int]:
    """Search stock.quant IDs with product_id and inventory_quantity_set=True."""
    domain = [
        ('product_id', '=', product_id),
        ('inventory_quantity_set', '=', True),
    ]
    return models.execute_kw(
        db, uid, password,
        'stock.quant', 'search',
        [domain],
        {'order': 'id'},
    )


def action_apply_inventory_batch(
    models,
    db: str,
    uid: int,
    password: str,
    quant_ids: List[int],
    inventory_name: Optional[str] = None,
) -> None:
    """Call action_apply_inventory on the given stock.quant IDs (same as Apply button)."""
    if not quant_ids:
        return
    context = {
        # Skip conflict/track wizards so batch apply runs without opening dialogs
        'set_inventory_quantity_auto_apply': True,
    }
    if inventory_name is not None:
        context['inventory_name'] = inventory_name
    try:
        models.execute_kw(
            db, uid, password,
            'stock.quant', 'action_apply_inventory',
            [quant_ids],
            {'context': context},
        )
    except:
        pass


def run(
    product_id: int = DEFAULT_PRODUCT_ID,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    reference: Optional[str] = None,
) -> None:
    ref = reference if reference is not None else INVENTORY_ADJUSTMENT_REFERENCE
    common, models = get_connection(ODOO_URL)
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed")
    logger.info("Connected to %s DB=%s as uid=%s", ODOO_URL, ODOO_DB, uid)

    quant_ids = search_quants_to_apply(models, ODOO_DB, uid, ODOO_PASSWORD, product_id)
    total = len(quant_ids)
    logger.info("Found %s stock.quant records to apply for product_id=%s", total, product_id)
    if total == 0:
        logger.warning("No quants with inventory_quantity_set=True for product_id=%s", product_id)
        return

    if dry_run:
        logger.info("[DRY RUN] Would call action_apply_inventory in %s batches of up to %s (reference: %s)",
                    (total + batch_size - 1) // batch_size, batch_size, ref)
        return

    applied = 0
    for i in range(0, total, batch_size):
        batch = quant_ids[i : i + batch_size]
        try:
            action_apply_inventory_batch(
                models, ODOO_DB, uid, ODOO_PASSWORD,
                batch,
                inventory_name=ref,
            )
            applied += len(batch)
            logger.info("Applied batch %s: %s / %s quants", (i // batch_size) + 1, applied, total)
        except Exception as e:
            logger.error("Batch failed (quants %s..%s): %s", batch[0], batch[-1], e, exc_info=True)
            raise

    logger.info("Finished: applied inventory for %s quants (product_id=%s, reference=%s)",
                applied, product_id, ref)


def main():
    parser = argparse.ArgumentParser(
        description="Apply inventory adjustment for stock.quant by product_id (batch mode)."
    )
    parser.add_argument('--dry-run', action='store_true', help="Only report count, do not apply")
    parser.add_argument('--product-id', type=int, default=DEFAULT_PRODUCT_ID,
                        help=f"product.product id (default: {DEFAULT_PRODUCT_ID})")
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Quants per RPC call (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument('--reference', type=str, default=INVENTORY_ADJUSTMENT_REFERENCE,
                        help="Adjustment reference for stock moves")
    args = parser.parse_args()

    run(
        product_id=args.product_id,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        reference=args.reference,
    )
    logger.info("Done.")


if __name__ == '__main__':
    main()
