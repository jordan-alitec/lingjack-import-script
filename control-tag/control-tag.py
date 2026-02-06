#!/usr/bin/env python3
"""
Odoo 18 Control Tag Import – Inventory Adjustment (stock.lot + stock.quant)

Reads control-tag.xlsx: Com No (product default_code), Serial Range, No.
- Expands serial ranges (e.g. RW7507001-RW7508000 or RW7148988) into individual serials.
- For each serial: find or create stock.lot, then create/update stock.quant with quantity=1
  at the warehouse stock location (inventory adjustment).

Usage:
  python control-tag.py [--dry-run] [--no-apply] [--excel path] [--reference "Import From IND4"]
  --dry-run    : Log only, do not create/update Odoo records.
  --no-apply   : Set inventory_quantity on quants but do not call action_apply_inventory.
  --excel      : Path to control-tag Excel (default: control-tag.xlsx in script dir).
  --reference  : Adjustment reference shown on stock moves (default: "Import From IND4").
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pandas as pd
import xmlrpc.client

# Path setup: optional config from BOM parent
script_dir = Path(__file__).resolve().parent
bom_dir = script_dir.parent / "BOM"
if bom_dir.exists() and str(bom_dir) not in sys.path:
    sys.path.insert(0, str(bom_dir))

ODOO_URL = 'https://lingjack.odoo.com/'
ODOO_DB = 'alitecpteltd-lingjack-main-21976694'
ODOO_USERNAME = 'dataimport'
ODOO_PASSWORD = 'Admin@123456'

# ODOO_URL = 'http://localhost:8099'
# ODOO_DB = 'lingjack-test4'
# ODOO_USERNAME = 'dataimport'
# ODOO_PASSWORD = 'Admin@123456'

CONTROL_TAG_EXCEL = 'control-tag.xlsx'
WAREHOUSE_ID = 1
# Reference shown on the inventory adjustment (stock.move name)
INVENTORY_ADJUSTMENT_REFERENCE = 'Import From IND4'
DRY_RUN_DEFAULT = False
APPLY_INVENTORY_DEFAULT = True

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)
log_file_path = script_dir / 'import_control_tag_errors.log'
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(file_handler)


def normalize_com_no(value: Any) -> Optional[str]:
    """Convert Com No to string for lookup; None if empty/NaN."""
    if value is None or (hasattr(pd, 'isna') and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return str(int(value)).strip() or None
    return str(value).strip() or None


def parse_serial_range(cell: Any) -> List[str]:
    """
    Parse 'Serial Range' cell into a list of serial numbers.
    Supports: 'RW7507001-RW7508000', 'RW7149421 - RW7150000', 'RW7148988'.
    """
    if cell is None or (hasattr(pd, 'isna') and pd.isna(cell)):
        return []
    s = str(cell).strip()
    if not s:
        return []

    # Single serial (no hyphen) or range with hyphen
    if '-' in s:
        parts = [p.strip() for p in s.split('-', 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return generate_serial_range(parts[0], parts[1])
    return [s] if s else []


def generate_serial_range(start: str, end: str) -> List[str]:
    """Generate list of serials from start to end (e.g. RW7507001..RW7508000)."""
    if not start or not end:
        return []
    start = start.strip()
    end = end.strip()
    try:
        start_match = re.match(r'^(.+?)(\d+)$', start)
        end_match = re.match(r'^(.+?)(\d+)$', end)
        if start_match and end_match:
            start_prefix, start_num_str = start_match.groups()
            end_prefix, end_num_str = end_match.groups()
            if start_prefix != end_prefix:
                # Fallback: try plain integers
                try:
                    start_num = int(start)
                    end_num = int(end)
                except ValueError:
                    return []
                num_length = max(len(str(start_num)), len(str(end_num)))
                return [str(n).zfill(num_length) for n in range(start_num, end_num + 1)]
            start_num = int(start_num_str)
            end_num = int(end_num_str)
            num_length = len(start_num_str)
            if start_num > end_num:
                return []
            return [f"{start_prefix}{n:0{num_length}d}" for n in range(start_num, end_num + 1)]
        return []
    except (ValueError, AttributeError) as e:
        logger.debug("generate_serial_range %r..%r: %s", start, end, e)
        return []


def load_control_tag_serials(excel_path: Path) -> List[Tuple[str, str]]:
    """
    Load Excel and return list of (com_no, serial_name).
    Raises on missing columns or empty data.
    """
    df = pd.read_excel(excel_path, sheet_name=0, header=None)
    if df.shape[0] < 2:
        raise ValueError(f"No data rows in {excel_path}")
    df.columns = ['Com No', 'Serial Range', 'No.', 'Unit']
    df = df.iloc[1:].copy()
    df['Com No'] = df['Com No'].apply(normalize_com_no)

    out: List[Tuple[str, str]] = []
    for _, row in df.iterrows():
        com_no = row.get('Com No')
        if not com_no:
            continue
        serial_range_str = row.get('Serial Range')
        serials = parse_serial_range(serial_range_str)
        for serial in serials:
            if serial:
                out.append((com_no, serial))
    return out


class ControlTagImporter:
    """Import control-tag serials into Odoo as stock.lot + stock.quant (inventory adjustment)."""

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.uid = common.authenticate(db, username, password, {})
        if not self.uid:
            raise Exception(f"Authentication failed for user '{username}' on database '{db}'.")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        logger.info("Connected to Odoo DB '%s' as '%s'", db, username)

    def _search(self, model: str, domain: list, limit: Optional[int] = None) -> List[int]:
        kwargs = {}
        if limit is not None:
            kwargs['limit'] = limit
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search', [domain], kwargs
        )

    def _create(self, model: str, vals: dict) -> int:
        filtered = {k: v for k, v in vals.items() if v is not None}
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'create', [filtered]
        )

    def _write(self, model: str, ids: List[int], vals: dict) -> bool:
        filtered = {k: v for k, v in vals.items() if v is not None}
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'write', [ids, filtered]
        )

    def _read(self, model: str, ids: List[int], fields: List[str]) -> List[dict]:
        if not ids:
            return []
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'read', [ids], {'fields': fields}
        )

    def find_product_by_default_code(self, default_code: str) -> Optional[int]:
        ids = self._search(
            'product.product',
            [('default_code', '=', default_code)],
            limit=1
        )
        return ids[0] if ids else None

    def get_stock_location_warehouse(self, warehouse_id: int = WAREHOUSE_ID) -> Optional[int]:
        wh = self._read('stock.warehouse', [warehouse_id], ['lot_stock_id'])
        if not wh or not wh[0].get('lot_stock_id'):
            return None
        return wh[0]['lot_stock_id'][0]

    def find_or_create_lot(
        self,
        product_id: int,
        serial_name: str,
        dry_run: bool = False,
    ) -> Optional[int]:
        """Find or create stock.lot for product and serial name."""
        ids = self._search(
            'stock.lot',
            [('product_id', '=', product_id), ('name', '=', serial_name)],
            limit=1
        )
        if ids:
            return ids[0]
        if dry_run:
            logger.debug("[DRY RUN] Would create lot %s for product_id %s", serial_name, product_id)
            return None
        try:
            lot_id = self._create('stock.lot', {
                'product_id': product_id,
                'name': serial_name,
            })
            logger.debug("Created lot '%s' (ID %s)", serial_name, lot_id)
            return lot_id
        except Exception as e:
            logger.error("Failed to create lot '%s': %s", serial_name, e, exc_info=True)
            return None

    def set_quant_inventory(
        self,
        product_id: int,
        lot_id: int,
        location_id: int,
        quantity: float = 1.0,
        dry_run: bool = False,
    ) -> Optional[int]:
        """Create or update stock.quant with inventory_quantity (and inventory_quantity_set)."""
        if dry_run:
            logger.debug(
                "[DRY RUN] Would set quant product=%s lot=%s location=%s qty=%s",
                product_id, lot_id, location_id, quantity
            )
            return None
        quant_ids = self._search(
            'stock.quant',
            [
                ('product_id', '=', product_id),
                ('lot_id', '=', lot_id),
                ('location_id', '=', location_id),
            ],
            limit=1
        )
        try:
            vals = {
                'inventory_quantity': quantity,
                'inventory_quantity_set': True,
            }
            if quant_ids:
                self._write('stock.quant', quant_ids, vals)
                return quant_ids[0]
            quant_id = self._create('stock.quant', {
                'product_id': product_id,
                'lot_id': lot_id,
                'location_id': location_id,
                'inventory_quantity': quantity,
                'inventory_quantity_set': True,
            })
            logger.debug("Created quant ID %s for lot ID %s", quant_id, lot_id)
            return quant_id
        except Exception as e:
            logger.error(
                "Failed to set quant product=%s lot=%s: %s",
                product_id, lot_id, e, exc_info=True
            )
            return None

    def action_apply_inventory(
        self,
        quant_ids: List[int],
        dry_run: bool = False,
        adjustment_reference: Optional[str] = None,
    ) -> None:
        """Call action_apply_inventory on given stock.quant IDs with optional reference name."""
        if not quant_ids or dry_run:
            return
        ref = adjustment_reference if adjustment_reference is not None else INVENTORY_ADJUSTMENT_REFERENCE
        context = {'inventory_name': ref}
        try:
            self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.quant', 'action_apply_inventory',
                [quant_ids],
                {'context': context},
            )
            logger.info("Applied inventory for %s quants (reference: %s)", len(quant_ids), ref)
        except Exception as e:
            logger.error("action_apply_inventory failed: %s", e, exc_info=True)

    def run(
        self,
        serials: List[Tuple[str, str]],
        location_id: Optional[int] = None,
        dry_run: bool = False,
        apply_inventory: bool = True,
        adjustment_reference: Optional[str] = None,
    ) -> None:
        """Create/update lots and quants for each (com_no, serial); optionally apply inventory."""
        self._adjustment_reference = adjustment_reference if adjustment_reference is not None else INVENTORY_ADJUSTMENT_REFERENCE
        if not serials:
            logger.warning("No serials to import")
            return
        if location_id is None:
            location_id = self.get_stock_location_warehouse()
        if not location_id:
            raise RuntimeError("Could not resolve stock location for warehouse")

        product_cache: dict = {}
        applied_quant_ids: List[int] = []
        created_lots = 0
        updated_quants = 0
        errors = 0

        for i, (com_no, serial_name) in enumerate(serials):
            if (i + 1) % 500 == 0:
                logger.info("Progress: %s / %s", i + 1, len(serials))

            product_id = product_cache.get(com_no)
            if product_id is None:
                product_id = self.find_product_by_default_code(com_no)
                if not product_id:
                    logger.warning("Product not found for Com No '%s', serial '%s'", com_no, serial_name)
                    errors += 1
                    continue
                product_cache[com_no] = product_id

            lot_id = self.find_or_create_lot(product_id, serial_name, dry_run=dry_run)
            if not lot_id and not dry_run:
                errors += 1
                continue
            if lot_id and not dry_run:
                created_lots += 1

            quant_id = self.set_quant_inventory(
                product_id, lot_id, location_id, quantity=1.0, dry_run=dry_run
            )
            if quant_id:
                updated_quants += 1
                if apply_inventory:
                    applied_quant_ids.append(quant_id)

        logger.info(
            "Import summary: %s serials processed, lots created/found=%s, quants set=%s, errors=%s",
            len(serials), created_lots, updated_quants, errors
        )

        if apply_inventory and applied_quant_ids and not dry_run:
            # Apply in batches to avoid timeouts
            batch = 100
            for j in range(0, len(applied_quant_ids), batch):
                self.action_apply_inventory(
                    applied_quant_ids[j:j + batch],
                    dry_run=False,
                    adjustment_reference=getattr(self, '_adjustment_reference', None),
                )


def main():
    parser = argparse.ArgumentParser(description="Import control-tag.xlsx for inventory adjustment")
    parser.add_argument('--dry-run', action='store_true', help="Do not create/update Odoo records")
    parser.add_argument('--no-apply', action='store_true', help="Do not call action_apply_inventory")
    parser.add_argument('--excel', type=Path, default=script_dir / CONTROL_TAG_EXCEL, help="Path to control-tag Excel")
    parser.add_argument(
        '--reference',
        type=str,
        default=INVENTORY_ADJUSTMENT_REFERENCE,
        help="Adjustment reference shown on stock moves (default: %(default)s)",
    )
    args = parser.parse_args()

    excel_path = args.excel
    if not excel_path.is_absolute():
        excel_path = script_dir / excel_path
    if not excel_path.exists():
        logger.error("Excel not found: %s", excel_path)
        sys.exit(1)

    logger.info("Loading serials from %s", excel_path)
    serials = load_control_tag_serials(excel_path)
    logger.info("Loaded %s (com_no, serial) pairs", len(serials))
    if not serials:
        logger.warning("No serials to import")
        sys.exit(0)

    importer = ControlTagImporter(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    location_id = importer.get_stock_location_warehouse()
    if not location_id:
        logger.error("Stock location for warehouse %s not found", WAREHOUSE_ID)
        sys.exit(1)

    importer.run(
        serials,
        location_id=location_id,
        dry_run=args.dry_run,
        apply_inventory=not args.no_apply,
        adjustment_reference=args.reference,
    )
    logger.info("Control-tag import finished.")


if __name__ == '__main__':
    main()
