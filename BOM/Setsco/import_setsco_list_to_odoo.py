#!/usr/bin/env python3
"""
Odoo 18 SetscoList.xlsx Import Script

Reads serial number ranges from SetscoList.xlsx (sheets: Office, Warehouse, Production)
and creates/updates setsco.serial.number records via XML-RPC.

- Office: range import with setsco category (Column G = Setco Category).
- Warehouse: tie product (Com No) and location by name under warehouse_id=1.
- Production: search mrp.production by PWO; if found tie to MO (like assignment wizard),
  else location = Stock in warehouse 1. All PWO outcomes go to notes.

Pre-run (--pre-run): validate Com No and location/category before import.
"""

import argparse
import sys
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import xmlrpc.client
import pandas as pd

# Path setup for config
script_dir = Path(__file__).parent
bom_dir = script_dir.parent
if str(bom_dir) not in sys.path:
    sys.path.insert(0, str(bom_dir))

try:
    import config
    ODOO_URL = getattr(config, 'ODOO_URL', 'http://localhost:8069')
    ODOO_DB = getattr(config, 'ODOO_DB', 'your_database_name')
    ODOO_USERNAME = getattr(config, 'ODOO_USERNAME', 'admin')
    ODOO_PASSWORD = getattr(config, 'ODOO_PASSWORD', 'admin')
    DRY_RUN = getattr(config, 'SETSCO_DRY_RUN', True)
    SETSCO_LIST_EXCEL_FILE = getattr(config, 'SETSCO_LIST_EXCEL_FILE', 'SetscoList.xlsx')
except ImportError:
    ODOO_URL = 'http://localhost:8099'
    ODOO_DB = 'lingjack-run'
    ODOO_USERNAME = 'dataimport'
    ODOO_PASSWORD = 'Admin@12345678'
    DRY_RUN = True
    SETSCO_LIST_EXCEL_FILE = 'SetscoList.xlsx'

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)
log_file_path = script_dir / 'import_setsco_list_errors.log'
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(file_handler)

# Column names in SetscoList.xlsx (from actual file)
COL_COM_NO = 'Com No'
COL_START = 'Start'
COL_END = 'End'
COL_LOCATION = 'Location'
COL_LOCATION2 = 'Location2'
COL_PWO = 'PWO number'
COL_SETCO_CATEGORY = 'Setco Category'

SHEET_OFFICE = 'Office'
SHEET_WAREHOUSE = 'Warehouse'
SHEET_PRODUCTION = 'Production'
SHEETS_ORDER = [SHEET_OFFICE, SHEET_WAREHOUSE, SHEET_PRODUCTION]

WAREHOUSE_ID = 1


def _normalize_com_no(value: Any) -> Optional[str]:
    """Convert Com No to string for lookup; None if empty/NaN."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    return str(value).strip() or None


# Import base importer after path is set
import import_setsco_serials_to_odoo as base_module
SetscoSerialImporter = base_module.SetscoSerialImporter


class SetscoListImporter(SetscoSerialImporter):
    """Import from SetscoList.xlsx (Office, Warehouse, Production sheets)."""

    # --------------- New helpers (location / warehouse / production) ---------------

    def _read(self, model: str, ids: List[int], fields: List[str]) -> List[dict]:
        """Read records from Odoo."""
        if not ids:
            return []
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'read',
            [ids],
            {'fields': fields}
        )

    def find_location_by_name_and_warehouse(self, location_name: str, warehouse_id: int = WAREHOUSE_ID) -> Optional[int]:
        """Find stock.location by name under warehouse view (child_of view_location_id)."""
        if not location_name or pd.isna(location_name):
            return None
        location_name = str(location_name).strip()
        if not location_name:
            return None
        # Get warehouse view_location_id
        wh = self._read('stock.warehouse', [warehouse_id], ['view_location_id'])
        if not wh or not wh[0].get('view_location_id'):
            logger.warning(f"Warehouse {warehouse_id} or view_location_id not found")
            return None
        view_location_id = wh[0]['view_location_id'][0]
        # Search location by name under that view (child_of)
        location_ids = self._search(
            'stock.location',
            [('name', '=', location_name), ('id', 'child_of', view_location_id)],
            limit=1
        )
        if location_ids:
            logger.debug(f"Found location '{location_name}' under warehouse {warehouse_id}: ID {location_ids[0]}")
            return location_ids[0]
        logger.warning(f"No location named '{location_name}' under warehouse {warehouse_id}")
        return None

    def get_stock_location_warehouse_1(self) -> Optional[int]:
        """Return stock location (lot_stock_id) for warehouse_id=1."""
        wh = self._read('stock.warehouse', [WAREHOUSE_ID], ['lot_stock_id'])
        if not wh or not wh[0].get('lot_stock_id'):
            logger.warning("Warehouse 1 or lot_stock_id not found")
            return None
        return wh[0]['lot_stock_id'][0]

    def find_production_by_name(self, pwo_name: str) -> Optional[int]:
        """Find mrp.production by name (PWO number)."""
        if not pwo_name or pd.isna(pwo_name):
            return None
        pwo_name = str(pwo_name).strip()
        if not pwo_name:
            return None
        ids = self._search('mrp.production', [('name', '=', pwo_name)], limit=1)
        if ids:
            logger.debug(f"Found production order '{pwo_name}': ID {ids[0]}")
            return ids[0]
        logger.debug(f"No production order found for '{pwo_name}'")
        return None

    def find_setsco_category_for_list(self, category_str: str) -> Optional[int]:
        """Find setsco.category by description (ilike) or by name (ilike). Used for Setco Category column."""
        if not category_str or pd.isna(category_str):
            return None
        category_str = str(category_str).strip()
        if not category_str:
            return None
        cat_id = self.find_setsco_category_by_description(category_str)
        if cat_id:
            return cat_id
        # Fallback: search by name ilike
        ids = self._search(
            'setsco.category',
            [('name', 'ilike', category_str)],
            limit=1
        )
        if ids:
            logger.debug(f"Found setsco.category by name '{category_str}': ID {ids[0]}")
            return ids[0]
        return None

    def _read_production_location_src(self, production_id: int) -> Optional[int]:
        """Get location_src_id for an mrp.production."""
        recs = self._read('mrp.production', [production_id], ['location_src_id'])
        if not recs or not recs[0].get('location_src_id'):
            return None
        return recs[0]['location_src_id'][0]

    # --------------- Extended create_serial_number (production_id, notes, manufacturing_date) ---------------

    def create_serial_number_list(
        self,
        serial_name: str,
        setsco_category_id: int,
        serial_type: str,
        location_id: Optional[int] = None,
        product_id: Optional[int] = None,
        state: str = 'new',
        production_id: Optional[int] = None,
        notes: Optional[str] = None,
        manufacturing_date: Optional[str] = None,
    ) -> Optional[int]:
        """Create or update setsco.serial.number with optional production_id, notes, manufacturing_date."""
        existing_ids = self._search(
            'setsco.serial.number',
            [('name', '=', serial_name)],
            limit=1
        )
        vals = {
            'name': serial_name,
            'serial_type': serial_type,
            'setsco_category_id': setsco_category_id,
            'state': state,
        }
        if location_id:
            vals['location_id'] = location_id
        if product_id:
            vals['product_id'] = product_id
        if production_id is not None:
            vals['production_id'] = production_id
        if notes is not None:
            vals['notes'] = notes
        if manufacturing_date is not None:
            vals['manufacturing_date'] = manufacturing_date

        if existing_ids:
            if DRY_RUN:
                logger.info(f"[DRY RUN] Would update serial number {serial_name}: {vals}")
                return existing_ids[0]
            self._write('setsco.serial.number', existing_ids, vals)
            return existing_ids[0]
        # Create new
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would create serial number: {vals}")
            return None
        try:
            return self._create('setsco.serial.number', vals)
        except Exception as e:
            logger.error(f"Failed to create serial number '{serial_name}': {e}")
            return None

    # --------------- Pre-run validation ---------------

    def pre_run(self, excel_file: str) -> Tuple[bool, List[str]]:
        """
        Validate all rows: Com No (when required) and location/category exist.
        Returns (passed, list_of_error_messages).
        """
        errors: List[str] = []
        if not Path(excel_file).exists():
            errors.append(f"Excel file not found: {excel_file}")
            return False, errors

        try:
            xl = pd.ExcelFile(excel_file)
        except Exception as e:
            errors.append(f"Failed to read Excel: {e}")
            return False, errors

        # Check warehouse 1 and Stock location once
        stock_location_id = self.get_stock_location_warehouse_1()
        if stock_location_id is None:
            errors.append("Warehouse 1 or its Stock location (lot_stock_id) not found in Odoo.")

        for sheet_name in SHEETS_ORDER:
            if sheet_name not in xl.sheet_names:
                errors.append(f"Sheet '{sheet_name}' not found in Excel.")
                continue
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            required_cols = [COL_COM_NO, COL_START, COL_END, COL_SETCO_CATEGORY]
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                errors.append(f"Sheet '{sheet_name}': missing columns {missing}.")
                continue

            for idx, row in df.iterrows():
                row_num = idx + 2  # 1-based + header
                com_no_raw = row.get(COL_COM_NO)
                com_no = _normalize_com_no(com_no_raw)
                start = row.get(COL_START)
                end = row.get(COL_END)
                category_val = row.get(COL_SETCO_CATEGORY)
                location_val = row.get(COL_LOCATION)

                # Skip empty range rows
                if pd.isna(start) or pd.isna(end):
                    continue

                # Office: Com No can be empty; category required
                if sheet_name == SHEET_OFFICE:
                    if pd.isna(category_val) or not str(category_val).strip():
                        errors.append(f"{sheet_name} row {row_num}: Setco Category is empty.")
                    else:
                        cat_id = self.find_setsco_category_for_list(str(category_val).strip())
                        if not cat_id:
                            errors.append(f"{sheet_name} row {row_num}: Setco Category '{category_val}' not found.")
                    if com_no is not None:
                        if not self.find_product_by_default_code(com_no_raw):
                            errors.append(f"{sheet_name} row {row_num}: Com No '{com_no}' not found.")
                    continue

                # Warehouse: Com No and location required
                if sheet_name == SHEET_WAREHOUSE:
                    if com_no is None:
                        errors.append(f"{sheet_name} row {row_num}: Com No is empty.")
                    else:
                        if not self.find_product_by_default_code(com_no_raw):
                            errors.append(f"{sheet_name} row {row_num}: Com No '{com_no}' not found.")
                    if pd.isna(category_val) or not str(category_val).strip():
                        errors.append(f"{sheet_name} row {row_num}: Setco Category is empty.")
                    else:
                        cat_id = self.find_setsco_category_for_list(str(category_val).strip())
                        if not cat_id:
                            errors.append(f"{sheet_name} row {row_num}: Setco Category '{category_val}' not found.")
                    loc_name = location_val if not pd.isna(location_val) else row.get(COL_LOCATION2)
                    if pd.isna(loc_name) or not str(loc_name).strip():
                        errors.append(f"{sheet_name} row {row_num}: Location is empty.")
                    else:
                        if not self.find_location_by_name_and_warehouse(str(loc_name).strip()):
                            errors.append(f"{sheet_name} row {row_num}: Location '{loc_name}' not found under warehouse {WAREHOUSE_ID}.")
                    continue

                # Production: Com No and category required; location used only when no MO (Stock wh1)
                if sheet_name == SHEET_PRODUCTION:
                    if com_no is None:
                        errors.append(f"{sheet_name} row {row_num}: Com No is empty.")
                    else:
                        if not self.find_product_by_default_code(com_no_raw):
                            errors.append(f"{sheet_name} row {row_num}: Com No '{com_no}' not found.")
                    if pd.isna(category_val) or not str(category_val).strip():
                        errors.append(f"{sheet_name} row {row_num}: Setco Category is empty.")
                    else:
                        cat_id = self.find_setsco_category_for_list(str(category_val).strip())
                        if not cat_id:
                            errors.append(f"{sheet_name} row {row_num}: Setco Category '{category_val}' not found.")
                    if stock_location_id is None:
                        errors.append(f"{sheet_name} row {row_num}: Stock location for warehouse 1 not available (used when PWO not found).")

        passed = len(errors) == 0
        return passed, errors

    # --------------- Sheet import logic ---------------

    def import_sheet_office(self, df: pd.DataFrame, stats: dict) -> None:
        """Office: range import with setsco category from Setco Category column."""
        for idx, row in df.iterrows():
            try:
                start, end = row.get(COL_START), row.get(COL_END)
                if pd.isna(start) or pd.isna(end):
                    continue
                category_val = row.get(COL_SETCO_CATEGORY)
                if pd.isna(category_val) or not str(category_val).strip():
                    stats['errors'] += 1
                    continue
                setsco_category_id = self.find_setsco_category_for_list(str(category_val).strip())
                if not setsco_category_id:
                    stats['errors'] += 1
                    continue
                com_no_raw = row.get(COL_COM_NO)
                product_id = None
                if com_no_raw is not None and not pd.isna(com_no_raw):
                    product_id = self.find_product_by_default_code(com_no_raw)
                serial_type = self.determine_serial_type(str(category_val))
                serial_names = self.generate_serial_range(start, end)
                if not serial_names:
                    stats['errors'] += 1
                    continue
                state = 'warehouse' if product_id else 'new'
                for serial_name in serial_names:
                    sid = self.create_serial_number_list(
                        serial_name=serial_name,
                        setsco_category_id=setsco_category_id,
                        serial_type=serial_type,
                        product_id=product_id,
                        state=state,
                    )
                    if sid:
                        stats['total_serials_created'] += 1
                stats['processed_rows'] += 1
            except Exception as e:
                logger.error(f"Office row {idx + 2}: {e}", exc_info=True)
                stats['errors'] += 1

    def import_sheet_warehouse(self, df: pd.DataFrame, stats: dict) -> None:
        """Warehouse: product (Com No) + location by name under warehouse 1."""
        for idx, row in df.iterrows():
            try:
                start, end = row.get(COL_START), row.get(COL_END)
                if pd.isna(start) or pd.isna(end):
                    continue
                com_no_raw = row.get(COL_COM_NO)
                com_no = _normalize_com_no(com_no_raw)
                if not com_no:
                    stats['errors'] += 1
                    continue
                product_id = self.find_product_by_default_code(com_no_raw)
                if not product_id:
                    stats['errors'] += 1
                    continue
                category_val = row.get(COL_SETCO_CATEGORY)
                if pd.isna(category_val) or not str(category_val).strip():
                    stats['errors'] += 1
                    continue
                setsco_category_id = self.find_setsco_category_for_list(str(category_val).strip())
                if not setsco_category_id:
                    stats['errors'] += 1
                    continue
                loc_name = row.get(COL_LOCATION)
                if pd.isna(loc_name):
                    loc_name = row.get(COL_LOCATION2)
                if pd.isna(loc_name) or not str(loc_name).strip():
                    stats['errors'] += 1
                    continue
                location_id = self.find_location_by_name_and_warehouse(str(loc_name).strip())
                if not location_id:
                    stats['errors'] += 1
                    continue
                serial_type = self.determine_serial_type(str(category_val))
                serial_names = self.generate_serial_range(start, end)
                if not serial_names:
                    stats['errors'] += 1
                    continue
                for serial_name in serial_names:
                    sid = self.create_serial_number_list(
                        serial_name=serial_name,
                        setsco_category_id=setsco_category_id,
                        serial_type=serial_type,
                        location_id=location_id,
                        product_id=product_id,
                        state='warehouse',
                    )
                    if sid:
                        stats['total_serials_created'] += 1
                stats['processed_rows'] += 1
            except Exception as e:
                logger.error(f"Warehouse row {idx + 2}: {e}", exc_info=True)
                stats['errors'] += 1

    def import_sheet_production(self, df: pd.DataFrame, stats: dict) -> None:
        """Production: PWO lookup; if found tie to MO (like assignment wizard), else Stock wh1. Notes = PWO found/not found."""
        from datetime import datetime
        stock_location_id = self.get_stock_location_warehouse_1()
        for idx, row in df.iterrows():
            try:
                start, end = row.get(COL_START), row.get(COL_END)
                if pd.isna(start) or pd.isna(end):
                    continue
                com_no_raw = row.get(COL_COM_NO)
                com_no = _normalize_com_no(com_no_raw)
                if not com_no:
                    stats['errors'] += 1
                    continue
                product_id = self.find_product_by_default_code(com_no_raw)
                if not product_id:
                    stats['errors'] += 1
                    continue
                category_val = row.get(COL_SETCO_CATEGORY)
                if pd.isna(category_val) or not str(category_val).strip():
                    stats['errors'] += 1
                    continue
                setsco_category_id = self.find_setsco_category_for_list(str(category_val).strip())
                if not setsco_category_id:
                    stats['errors'] += 1
                    continue
                pwo_raw = row.get(COL_PWO)
                pwo_name = str(pwo_raw).strip() if pwo_raw is not None and not pd.isna(pwo_raw) else None
                production_id = self.find_production_by_name(pwo_name) if pwo_name else None
                # Build notes: all PWO (found or not)
                if pwo_name:
                    pwo_note = f"PWO: {pwo_name} (found)" if production_id else f"PWO: {pwo_name} (not found)"
                else:
                    pwo_note = "PWO: (empty)"
                serial_type = self.determine_serial_type(str(category_val))
                serial_names = self.generate_serial_range(start, end)
                if not serial_names:
                    stats['errors'] += 1
                    continue
                if production_id:
                    location_src_id = self._read_production_location_src(production_id)
                    location_id = location_src_id
                    state = 'manufacturing'
                    manufacturing_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                else:
                    location_id = stock_location_id
                    state = 'warehouse'
                    production_id = False
                    manufacturing_date = None
                for serial_name in serial_names:
                    sid = self.create_serial_number_list(
                        serial_name=serial_name,
                        setsco_category_id=setsco_category_id,
                        serial_type=serial_type,
                        location_id=location_id,
                        product_id=product_id,
                        state=state,
                        production_id=production_id if production_id else None,
                        notes=pwo_note,
                        manufacturing_date=manufacturing_date,
                    )
                    if sid:
                        stats['total_serials_created'] += 1
                stats['processed_rows'] += 1
            except Exception as e:
                logger.error(f"Production row {idx + 2}: {e}", exc_info=True)
                stats['errors'] += 1

    def import_from_excel(self, excel_file: str, force: bool = False) -> bool:
        """
        Run pre-run; if pass (or force), import all three sheets.
        Returns True if import ran successfully.
        """
        logger.info("=" * 80)
        logger.info("SetscoList.xlsx Import")
        logger.info(f"Excel file: {excel_file}")
        logger.info(f"Dry run: {DRY_RUN}")
        logger.info("=" * 80)

        if not Path(excel_file).exists():
            logger.error(f"Excel file not found: {excel_file}")
            return False

        passed, errors = self.pre_run(excel_file)
        for err in errors:
            logger.error(err)
        if not passed and not force:
            logger.error("Pre-run failed. Fix errors above or run with --force to skip validation.")
            return False
        if not passed and force:
            logger.warning("Pre-run had errors but continuing (--force).")

        try:
            xl = pd.ExcelFile(excel_file)
        except Exception as e:
            logger.error(f"Failed to read Excel: {e}")
            return False

        stats = {'total_rows': 0, 'processed_rows': 0, 'total_serials_created': 0, 'errors': 0}
        for sheet_name in SHEETS_ORDER:
            if sheet_name not in xl.sheet_names:
                continue
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            stats['total_rows'] += len(df)
            logger.info(f"Processing sheet: {sheet_name} ({len(df)} rows)")
            if sheet_name == SHEET_OFFICE:
                self.import_sheet_office(df, stats)
            elif sheet_name == SHEET_WAREHOUSE:
                self.import_sheet_warehouse(df, stats)
            elif sheet_name == SHEET_PRODUCTION:
                self.import_sheet_production(df, stats)

        logger.info("=" * 80)
        logger.info("IMPORT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total rows processed: {stats['processed_rows']}/{stats['total_rows']}")
        logger.info(f"Total serials created/updated: {stats['total_serials_created']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("=" * 80)
        return True


def main():
    parser = argparse.ArgumentParser(description='Import SetscoList.xlsx to Odoo setsco.serial.number')
    parser.add_argument('--pre-run', action='store_true', help='Only run validation; do not import')
    parser.add_argument('--force', action='store_true', help='Run import even if pre-run fails')
    parser.add_argument('--file', type=str, default=None, help='Path to SetscoList.xlsx (default: config)')
    args = parser.parse_args()

    excel_file = args.file or str(script_dir / SETSCO_LIST_EXCEL_FILE)
    if not Path(excel_file).exists() and not args.file:
        excel_file = str(script_dir / 'SetscoList.xlsx')

    try:
        importer = SetscoListImporter(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
        if args.pre_run:
            passed, errors = importer.pre_run(excel_file)
            for err in errors:
                logger.error(err)
            logger.info("Pre-run: %s", "PASSED" if passed else "FAILED")
            return 0 if passed else 1
        success = importer.import_from_excel(excel_file, force=args.force)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
