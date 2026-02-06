#!/usr/bin/env python3
"""
Odoo 18 QRServiceReport.xlsx Servicing List Import Script (Servicing List/)

Reads QRServiceReport.xlsx and creates records in:
- x_fe_service_in_house when Column F (Service Centre) contains "LJ Engineering"
- x_fe_service_onsite otherwise

Field mapping (same for both models):
  Column A -> x_studio_service_id
  Column B -> x_studio_product_type (many2one x_product_type_fe by x_name)
  Column C -> x_studio_setsco_no
  Column D -> x_studio_control_tag_name
  Column E -> x_studio_customer_name
  Column H -> x_studio_remarks
  Column I -> x_studio_date_service; x_studio_date_next_service = date + 1 year

Dry run (--dry-run): validate that all product types (Column B) exist in x_product_type_fe
before import. Use before running actual import.

Note: If your Odoo uses x_studio_control_tag instead of x_studio_control_tag_name, or
if the onsite model is x_fe_service instead of x_fe_service_onsite, adjust the constants
and field keys in _row_to_vals().
"""

import argparse
import sys
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import xmlrpc.client
import pandas as pd

# Path setup
script_dir = Path(__file__).resolve().parent

# Odoo connection (override via env or config if needed)
ODOO_URL = 'http://localhost:8099'
ODOO_DB = 'lingjack-migration-2'
ODOO_USERNAME = 'dataimport'
ODOO_PASSWORD = 'Admin@123456'

# ODOO_URL = 'https://lingjack.odoo.com/'
# ODOO_DB = 'alitecpteltd-lingjack-main-21976694'
# ODOO_USERNAME = 'dataimport'
# ODOO_PASSWORD = 'Admin@123456'

# Model names: if your onsite model is x_fe_service instead of x_fe_service_onsite, change below
MODEL_IN_HOUSE = 'x_fe_service_in_house'
MODEL_ONSITE = 'x_fe_service_onsite'

# Excel column names (QRServiceReport.xlsx header row)
COL_QR_CODE = 'QR Code'                    # A -> x_studio_service_id
COL_SERVICE_PRODUCT_NAME = 'Service Product Name'  # B -> x_studio_product_type (x_name)
COL_SETSCO_NO = 'SETSCO No'                # C -> x_studio_setsco_no
COL_TAG_NO = 'Tag No'                      # D -> x_studio_control_tag_name
COL_CUSTOMER_NAME = 'Customer Name'        # E -> x_studio_customer_name
COL_SERVICE_CENTRE = 'Service Centre'      # F -> routing: LJ Engineering -> in_house else onsite
COL_QR_REMARKS = 'QR Remarks'              # H -> x_studio_remarks
COL_UPDATED_DATE = 'Updated Date'          # I -> x_studio_date_service, +1y -> x_studio_date_next_service

LJ_ENGINEERING_MARKER = 'LJ Engineering'
DEFAULT_EXCEL_FILE = 'QRServiceReport.xlsx'
# Rows skipped due to missing product type are written here (same folder as this script)
SKIPPED_PRODUCT_TYPE_EXCEL = 'servicing_list_skipped_product_type.xlsx'

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)
log_file_path = script_dir / 'import_servicing_list_errors.log'
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(file_handler)


def _normalize_str(value: Any) -> Optional[str]:
    """Return stripped string or None for empty/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if value == value else None  # avoid NaN
    s = str(value).strip()
    return s or None


def _parse_date(value: Any) -> Optional[date]:
    """Parse Excel date/datetime to date. Returns None if invalid or empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%d/%m/%Y'):
                try:
                    return datetime.strptime(value.strip()[:19], fmt).date()
                except ValueError:
                    continue
        return pd.Timestamp(value).date()
    except Exception:
        return None


class ServicingListImporter:
    """Import QRServiceReport.xlsx to Odoo x_fe_service_in_house / x_fe_service_onsite via XML-RPC."""

    def __init__(self, url: str, db: str, username: str, password: str):
        """Initialize Odoo XML-RPC connection."""
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

    def _search(self, model: str, domain: list, limit: int = 1) -> List[int]:
        """Search records in Odoo."""
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search', [domain], {'limit': limit}
        )

    def _search_read(
        self,
        model: str,
        domain: list,
        fields: List[str],
        limit: Optional[int] = None,
    ) -> List[dict]:
        """Search and read in one call."""
        kwargs = {'fields': fields}
        if limit is not None:
            kwargs['limit'] = limit
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search_read', [domain], kwargs
        )

    def _create(self, model: str, vals: dict) -> int:
        """Create a record in Odoo."""
        filtered_vals = {k: v for k, v in vals.items() if v is not None}
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'create', [filtered_vals]
        )

    def find_product_type_by_name(self, name: str) -> Optional[int]:
        """Find x_product_type_fe id by x_name (exact match)."""
        if not name:
            return None
        name = _normalize_str(name)
        if not name:
            return None
        ids = self._search('x_product_type_fe', [('x_name', '=', name)], limit=1)
        return ids[0] if ids else None

    def dry_run_product_types(self, excel_path: str) -> Tuple[bool, List[str]]:
        """
        Validate that every unique product type (Column B) in the Excel exists in x_product_type_fe.
        Returns (all_found, list of error messages).
        """
        errors: List[str] = []
        if not Path(excel_path).exists():
            errors.append(f"Excel file not found: {excel_path}")
            return False, errors
        try:
            df = pd.read_excel(excel_path)
        except Exception as e:
            errors.append(f"Failed to read Excel: {e}")
            return False, errors
        if COL_SERVICE_PRODUCT_NAME not in df.columns:
            errors.append(f"Column '{COL_SERVICE_PRODUCT_NAME}' (Column B) not found.")
            return False, errors
        unique_types = df[COL_SERVICE_PRODUCT_NAME].dropna().astype(str).str.strip().unique()
        missing = []
        for i, product_name in enumerate(unique_types):
            if not product_name:
                continue
            pid = self.find_product_type_by_name(product_name)
            if not pid:
                missing.append(product_name)
        if missing:
            errors.append(
                f"Product types not found in x_product_type_fe (x_name): {len(missing)} missing. "
                "Create them first or fix names in Excel."
            )
            for m in missing[:50]:
                errors.append(f"  - {m}")
            if len(missing) > 50:
                errors.append(f"  ... and {len(missing) - 50} more.")
        return len(missing) == 0, errors

    def _row_to_vals(
        self,
        row: pd.Series,
        product_type_id: Optional[int],
        dry_run: bool,
    ) -> Optional[dict]:
        """
        Build create vals for one row. Uses same field set for in_house and onsite.
        If product_type_id is None and Column B is filled, returns None (skip).
        """
        service_id = _normalize_str(row.get(COL_QR_CODE))
        if not service_id:
            return None
        product_name = _normalize_str(row.get(COL_SERVICE_PRODUCT_NAME))
        if product_name and product_type_id is None:
            return None  # required product type missing
        setsco_no = _normalize_str(row.get(COL_SETSCO_NO))
        control_tag = _normalize_str(row.get(COL_TAG_NO))
        customer_name = _normalize_str(row.get(COL_CUSTOMER_NAME))
        remarks = _normalize_str(row.get(COL_QR_REMARKS))
        date_service = _parse_date(row.get(COL_UPDATED_DATE))
        date_next = None
        if date_service:
            try:
                from datetime import timedelta
                # +1 year (approximate: 365 days; for exact calendar year use relativedelta)
                date_next = date(date_service.year + 1, date_service.month, date_service.day)
            except Exception:
                pass
        # Prefer user's field names; Odoo may use x_studio_control_tag instead of x_studio_control_tag_name
        vals = {
            'x_studio_service_id': service_id,
            'x_studio_setsco_no': setsco_no,
            'x_studio_control_tag_name': control_tag,
            'x_studio_customer_name': customer_name,
            'x_studio_remarks': remarks,
            'x_studio_date_service': date_service.isoformat() if date_service else None,
            'x_studio_date_next_service': date_next.isoformat() if date_next else None,
        }
        if product_type_id is not None:
            vals['x_studio_product_type'] = product_type_id
        return vals

    def _is_in_house(self, row: pd.Series) -> bool:
        """True if Column F (Service Centre) contains 'LJ Engineering'."""
        val = row.get(COL_SERVICE_CENTRE)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return False
        return LJ_ENGINEERING_MARKER.lower() in str(val).strip().lower()

    def import_from_excel(self, excel_path: str, dry_run: bool = False) -> bool:
        """
        Run dry-run validation first; then create records.
        - If dry_run: only validate product types and log what would be created (no create).
        """
        logger.info("=" * 80)
        logger.info("QRServiceReport.xlsx Servicing List Import")
        logger.info("Excel: %s", excel_path)
        logger.info("Dry run: %s", dry_run)
        logger.info("=" * 80)
        if not Path(excel_path).exists():
            logger.error("Excel file not found: %s", excel_path)
            return False
        try:
            df = pd.read_excel(excel_path)
        except Exception as e:
            logger.error("Failed to read Excel: %s", e)
            return False
        required = [COL_QR_CODE, COL_SERVICE_PRODUCT_NAME, COL_SERVICE_CENTRE]
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.error("Missing columns: %s", missing)
            return False
        if dry_run:
            passed, errs = self.dry_run_product_types(excel_path)
            for e in errs:
                logger.error("%s", e)
            if not passed:
                logger.error("Dry run: not all product types exist in x_product_type_fe (see above).")
                return False
        stats = {'in_house': 0, 'onsite': 0, 'errors': 0, 'skipped': 0, 'skipped_product_type': 0}
        skipped_product_type_rows: List[pd.Series] = []
        for idx, row in df.iterrows():
            row_num = idx + 2
            try:
                service_id = _normalize_str(row.get(COL_QR_CODE))
                if not service_id:
                    stats['skipped'] += 1
                    continue
                product_name = _normalize_str(row.get(COL_SERVICE_PRODUCT_NAME))
                product_type_id = self.find_product_type_by_name(product_name) if product_name else None
                if product_name and product_type_id is None:
                    logger.warning("Row %s: product type '%s' not found; skip and add to skipped list.", row_num, product_name)
                    row_with_reason = row.copy()
                    row_with_reason['Skip reason'] = f"Product type not found in x_product_type_fe: {product_name}"
                    skipped_product_type_rows.append(row_with_reason)
                    stats['skipped_product_type'] += 1
                    continue
                vals = self._row_to_vals(row, product_type_id, dry_run)
                if not vals:
                    stats['skipped'] += 1
                    continue
                is_in_house = self._is_in_house(row)
                model = MODEL_IN_HOUSE if is_in_house else MODEL_ONSITE
                if dry_run:
                    logger.info("[DRY RUN] Row %s would create %s: %s", row_num, model, vals)
                    if is_in_house:
                        stats['in_house'] += 1
                    else:
                        stats['onsite'] += 1
                    continue
                try:
                    self._create(model, vals)
                    if is_in_house:
                        stats['in_house'] += 1
                    else:
                        stats['onsite'] += 1
                except Exception as e:
                    logger.error("Row %s create failed (%s): %s", row_num, model, e)
                    stats['errors'] += 1
            except Exception as e:
                logger.error("Row %s error: %s", row_num, e, exc_info=True)
                stats['errors'] += 1
        if skipped_product_type_rows:
            skipped_path = (script_dir / SKIPPED_PRODUCT_TYPE_EXCEL).resolve()
            try:
                # Build from list of dicts so columns and data align; preserve original columns + Skip reason
                skipped_dicts = [s.to_dict() for s in skipped_product_type_rows]
                skipped_df = pd.DataFrame(skipped_dicts)
                skipped_df.to_excel(skipped_path, index=False)
                logger.info("Skipped rows (product type not found) written to: %s (%s rows)", skipped_path, len(skipped_product_type_rows))
            except Exception as e:
                logger.error("Failed to write skipped-product-type Excel: %s", e, exc_info=True)
        logger.info("=" * 80)
        logger.info("IMPORT SUMMARY")
        logger.info("  In-house (%s): %s", MODEL_IN_HOUSE, stats['in_house'])
        logger.info("  Onsite (%s): %s", MODEL_ONSITE, stats['onsite'])
        logger.info("  Errors: %s", stats['errors'])
        logger.info("  Skipped (product type not found): %s -> %s", stats['skipped_product_type'], (script_dir / SKIPPED_PRODUCT_TYPE_EXCEL).resolve())
        logger.info("  Skipped (other): %s", stats['skipped'])
        logger.info("=" * 80)
        return stats['errors'] == 0


def main():
    parser = argparse.ArgumentParser(
        description='Import QRServiceReport.xlsx to Odoo (x_fe_service_in_house / x_fe_service_onsite)'
    )
    parser.add_argument('--dry-run', action='store_true', help='Only validate product types and log would-be creates')
    parser.add_argument('--file', type=str, default=None, help=f'Path to Excel (default: {DEFAULT_EXCEL_FILE} in script dir)')
    args = parser.parse_args()
    excel_file = args.file or str(script_dir / DEFAULT_EXCEL_FILE)
    try:
        importer = ServicingListImporter(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
        success = importer.import_from_excel(excel_file, dry_run=args.dry_run)
        return 0 if success else 1
    except Exception as e:
        logger.error("Import failed: %s", e, exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
