#!/usr/bin/env python3
"""
Odoo 18 BoM Operation Update Script

Reads operations from an Excel file (e.g. output.xlsx) and
calls mrp.bom.api_update_operation_to_bom via XML-RPC.
"""

import sys
import logging
from typing import Dict, List, Optional

import xmlrpc.client
from openpyxl import load_workbook


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OdooBoMOperationUpdater:
    """Update BoM operations in Odoo 18 from Excel"""

    def __init__(self, url: str, db: str, username: str, password: str):
        """
        Initialize Odoo connection

        Args:
            url: Odoo server URL (e.g., 'http://localhost:8069')
            db: Database name
            username: Odoo username
            password: Odoo password
        """
        self.url = url
        self.db = db
        self.username = username
        self.password = password

        # Authenticate
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.uid = common.authenticate(db, username, password, {})
        if not self.uid:
            raise Exception(
                f"Authentication failed for user '{username}' "
                f"on database '{db}'."
            )

        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        logger.info("Connected to Odoo DB '%s' as '%s'", db, username)

    def _extract_operation_from_row(
        self,
        row_cells,
        operation_col: int,
    ) -> Optional[str]:
        """
        Extract a single operation name from a row.

        Args:
            row_cells: List of cell values for the row
            operation_col: 1-based index of the operation column

        Returns:
            Operation name as string, or None if empty/invalid
        """
        values = list(row_cells)

        if not (1 <= operation_col <= len(values)):
            return None

        operation = values[operation_col - 1]
        if operation is None:
            return None

        operation = str(operation).strip()
        return operation if operation else None

    def update_operations_from_excel(
        self,
        excel_path: str,
        sheet_name: Optional[str] = None,
        header_row: int = 1,
        category_col: int = 1,
        operation_col: int = 2,
        dry_run: bool = True,
    ):
        """
        Read Excel and group operations by category, then call api_update_operation_to_bom.

        Handles the pattern where column A (category) is empty when same as previous row.

        Args:
            excel_path: Path to Excel file (e.g. 'output.xlsx')
            sheet_name: Sheet name (default: active sheet)
            header_row: Row number of the header (data starts at header_row+1)
            category_col: 1-based column index of lingjack product category (Column A)
            operation_col: 1-based column index of operation name (Column B)
            dry_run: If True, only log operations without calling Odoo
        """
        wb = load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb[sheet_name] if sheet_name else wb.active

        start_row = header_row + 1
        max_row = ws.max_row

        # Dictionary to group operations by category: {category: [operations]}
        category_operations: Dict[str, List[str]] = {}
        current_category: Optional[str] = None

        # First pass: collect all operations grouped by category
        for row_idx in range(start_row, max_row + 1):
            row_cells = [cell.value for cell in ws[row_idx]]

            # Extract category from column A
            if len(row_cells) >= category_col:
                category_value = row_cells[category_col - 1]
                if category_value is not None:
                    category_str = str(category_value).strip()
                    if category_str:
                        # New category found, update current
                        current_category = category_str

            # If no current category, skip this row
            if not current_category:
                continue

            # Extract operation from column B
            operation = self._extract_operation_from_row(row_cells, operation_col)
            if not operation:
                continue

            # Add operation to the category's list (avoid duplicates)
            if current_category not in category_operations:
                category_operations[current_category] = []

            if operation not in category_operations[current_category]:
                category_operations[current_category].append(operation)
                logger.debug(
                    "Row %s: Category '%s' -> Operation '%s'",
                    row_idx,
                    current_category,
                    operation,
                )

        wb.close()

        # Log summary
        logger.info("=" * 60)
        logger.info("Operations grouped by category:")
        logger.info("=" * 60)
        for category, operations in category_operations.items():
            logger.info(
                "Category: '%s' -> %d operations: %s",
                category,
                len(operations),
                operations,
            )
        logger.info("=" * 60)
        logger.info("Total categories found: %d", len(category_operations))

        if dry_run:
            logger.info("DRY RUN MODE - No records will be created in Odoo")
            return

        # Second pass: call Odoo API for each category
        updated_count = 0
        error_count = 0

        for category, operations in category_operations.items():
            if not operations:
                logger.warning(
                    "Category '%s' has no operations, skipping",
                    category,
                )
                continue

            logger.info(
                "Updating Odoo: Category '%s' with %d operations: %s",
                category,
                len(operations),
                operations,
            )

            # Call Odoo method: mrp.bom.api_update_operation_to_bom(name, operation_list)
            try:
                result = self.models.execute_kw(
                    self.db,
                    self.uid,
                    self.password,
                    "mrp.bom",
                    "api_update_operation_to_bom",
                    [category, operations],
                )
                logger.info(
                    "✓ Successfully updated category '%s': %s",
                    category,
                    result,
                )
                updated_count += 1
            except xmlrpc.client.Fault as e:
                logger.error(
                    "✗ Odoo fault updating category '%s': %s",
                    category,
                    e,
                )
                error_count += 1
            except Exception as e:
                logger.error(
                    "✗ Error updating category '%s': %s",
                    category,
                    e,
                    exc_info=True,
                )
                error_count += 1

        logger.info("=" * 60)
        logger.info("Update Summary:")
        logger.info("  Categories successfully updated: %d", updated_count)
        logger.info("  Categories with errors: %d", error_count)
        logger.info("=" * 60)


def main():
    """
    CLI entry point.

    Configuration is taken from the central config.py in the BOM directory.
    """
    # Load configuration from central config.py in BOM directory
    import sys
    import os
    from pathlib import Path
    
    # Get the BOM directory (parent of this script's directory)
    script_dir = Path(__file__).parent
    bom_dir = script_dir.parent
    config_path = bom_dir / 'config.py'
    
    # Add BOM directory to path to import config
    if str(bom_dir) not in sys.path:
        sys.path.insert(0, str(bom_dir))
    
    try:
        import config  # type: ignore

        ODOO_URL = getattr(config, "ODOO_URL", "http://localhost:8069")
        ODOO_DB = getattr(config, "ODOO_DB", "your_database_name")
        ODOO_USERNAME = getattr(config, "ODOO_USERNAME", "admin")
        ODOO_PASSWORD = getattr(config, "ODOO_PASSWORD", "admin")
        EXCEL_FILE = getattr(config, "OPERATION_EXCEL_FILE", "output.xlsx")
        SHEET_NAME = getattr(config, "OPERATION_SHEET_NAME", None)
        DRY_RUN = getattr(config, "OPERATION_DRY_RUN", True)
        CATEGORY_COL = getattr(config, "OPERATION_CATEGORY_COL", 1)
        OPERATION_COL = getattr(config, "OPERATION_COL", 2)
    except ImportError:
        logger.error(f"Failed to import config from {config_path}")
        logger.error("Please ensure config.py exists in the BOM directory")
        # Fallback defaults – update these for your environment
        ODOO_URL = "http://localhost:8099"
        ODOO_DB = "lingjack-test"
        ODOO_USERNAME = "admin"
        ODOO_PASSWORD = "admin"
        EXCEL_FILE = "output.xlsx"
        SHEET_NAME = None
        DRY_RUN = False
        CATEGORY_COL = 1  # Column A: Lingjack Product Category
        OPERATION_COL = 2  # Column B: Operation Name

    # CLI overrides: first positional arg = excel path, --execute to disable dry-run
    if len(sys.argv) > 1 and sys.argv[1] not in ("--execute", "--dry-run"):
        EXCEL_FILE = sys.argv[1]

    if "--execute" in sys.argv:
        DRY_RUN = False
    if "--dry-run" in sys.argv:
        DRY_RUN = True

    logger.info("Excel file: %s", EXCEL_FILE)
    logger.info("Dry run: %s", DRY_RUN)

    updater = OdooBoMOperationUpdater(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    updater.update_operations_from_excel(
        excel_path=EXCEL_FILE,
        sheet_name=SHEET_NAME,
        header_row=1,
        category_col=CATEGORY_COL,
        operation_col=OPERATION_COL,
        dry_run=DRY_RUN,
    )


if __name__ == "__main__":
    main()


