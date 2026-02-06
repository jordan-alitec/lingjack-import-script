#!/usr/bin/env python3
"""
Odoo 18 Setsco Serial Number Import Script

Reads serial number ranges from Setsco_Combined.xlsx and creates
setsco.serial.number records via XML-RPC.

Features:
- Creates serial number ranges from Start and End columns
- Matches Sheet Name to setsco.category by description
- Handles serial_type: 'tuv' for specific sheets, otherwise 'setsco'
- Creates/finds multi-layer stock locations (e.g., "WH/Stock/A10123")
"""

import sys
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

import xmlrpc.client
import pandas as pd

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Remove existing handlers to avoid duplicates
logger.handlers = []

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler
script_dir = Path(__file__).parent
log_file_path = script_dir / 'import_setsco_serials_errors.log'
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Load configuration
bom_dir = script_dir.parent
config_path = bom_dir / 'config.py'

if str(bom_dir) not in sys.path:
    sys.path.insert(0, str(bom_dir))

try:
    import config
    ODOO_URL = getattr(config, 'ODOO_URL', 'http://localhost:8069')
    ODOO_DB = getattr(config, 'ODOO_DB', 'your_database_name')
    ODOO_USERNAME = getattr(config, 'ODOO_USERNAME', 'admin')
    ODOO_PASSWORD = getattr(config, 'ODOO_PASSWORD', 'admin')
    DRY_RUN = getattr(config, 'SETSCO_DRY_RUN', True)
    SETSCO_EXCEL_FILE = getattr(config, 'SETSCO_EXCEL_FILE', 'Setsco_Combined.xlsx')
except ImportError:
    logger.warning(f"Failed to import config from {config_path}")
    ODOO_URL = 'http://localhost:8099'
    ODOO_DB = 'lingjack-run'
    ODOO_USERNAME = 'dataimport'
    ODOO_PASSWORD = 'Admin@12345678'
    DRY_RUN = True
    SETSCO_EXCEL_FILE = 'Setsco_Combined.xlsx'

# TUV sheet codes
TUV_SHEET_CODES = ['03071601', '03071602', '03071606']


class SetscoSerialImporter:
    """Import Setsco Serial Numbers from Excel to Odoo 18"""

    def __init__(self, url: str, db: str, username: str, password: str):
        """Initialize Odoo connection"""
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

    # ---------------- Generic helpers ------------------

    def _search(self, model: str, domain: list, limit: int = 1) -> List[int]:
        """Search records in Odoo"""
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search',
            [domain],
            {'limit': limit}
        )

    def _create(self, model: str, vals: dict) -> int:
        """Create a record in Odoo"""
        # Filter out None values - XML-RPC cannot marshal None
        filtered_vals = {k: v for k, v in vals.items() if v is not None}
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'create',
            [filtered_vals]
        )

    def _read(self, model: str, ids: List[int], fields: List[str]) -> List[dict]:
        """Read records from Odoo"""
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'read',
            [ids],
            {'fields': fields}
        )

    def _write(self, model: str, ids: List[int], vals: dict) -> bool:
        """Update records in Odoo"""
        filtered_vals = {k: v for k, v in vals.items() if v is not None}
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'write',
            [ids, filtered_vals]
        )

    # ---------------- Lookups ------------------

    def find_setsco_category_by_description(self, sheet_name: str) -> Optional[int]:
        """
        Find setsco.category by description using 'like' search
        
        Args:
            sheet_name: Sheet name from Excel (e.g., "03071600")
            
        Returns:
            Category ID or None if not found
        """
        if not sheet_name:
            return None
        
        sheet_name = str(sheet_name).strip()
        if not sheet_name:
            return None
        
        # Search for category where description contains the sheet name
        category_ids = self._search(
            'setsco.category',
            [('description', 'ilike', sheet_name)],
            limit=1
        )
        
        if category_ids:
            logger.debug(f"Found setsco.category for sheet '{sheet_name}': ID {category_ids[0]}")
            return category_ids[0]
        
        logger.warning(f"Nos setsco.category found for sheet '{sheet_name}'")
        return None

    def find_product_by_default_code(self, default_code) -> Optional[int]:
        """
        Find product.product by default_code
        
        Args:
            default_code: Product default code (Com No from Excel) - can be str, int, or float
            
        Returns:
            Product ID or None if not found
        """
        if default_code is None or pd.isna(default_code):
            return None
        
        # Convert to string, handling numeric types (Excel may store as float)
        if isinstance(default_code, (int, float)):
            # Convert to int first to remove decimal, then to string
            default_code = str(int(default_code))
        else:
            default_code = str(default_code).strip()
        
        if not default_code:
            return None
        
        product_ids = self._search(
            'product.product',
            [('default_code', '=', default_code)],
            limit=1
        )
        
        if product_ids:
            logger.debug(f"Found product with default_code '{default_code}': ID {product_ids[0]}")
            return product_ids[0]
        
        logger.warning(f"No product found with default_code '{default_code}'")
        return None

    def get_or_create_location(self, location_path: str) -> Optional[int]:
        """
        Get or create stock.location from multi-layer path (e.g., "WH/Stock/A10123")
        
        Args:
            location_path: Location path separated by "/" (e.g., "WH/Stock/A10123")
            
        Returns:
            Location ID or None if creation failed
        """
        if not location_path or pd.isna(location_path):
            return None
        
        location_path = str(location_path).strip()
        if not location_path:
            return None
        
        # Split path into parts
        parts = [p.strip() for p in location_path.split('/') if p.strip()]
        if not parts:
            return None
        
        # Get or create each level of the location hierarchy
        parent_id = None
        current_location_id = None
        
        for i, part in enumerate(parts):
            # Search for location with this name and parent
            
            domain = [('name', '=', part)]
            if parent_id:
                domain.append(('location_id', '=', parent_id))
            else:
                # Top level - try to find if it already exists as a top-level location
                # First check if it exists without parent
                top_level_domain = [('name', '=', part), ('location_id', '=', False)]
                top_level_ids = self._search('stock.location', top_level_domain, limit=1)
                if top_level_ids:
                    current_location_id = top_level_ids[0]
                    logger.debug(f"Found top-level location '{part}' (ID: {current_location_id})")
                    parent_id = current_location_id
                    continue
                
                # # If not found, we'll create it under Stock location
                # # Try to find Stock location
                # stock_location_ids = self._search(
                #     'stock.location',
                #     [('usage', '=', 'internal'), ('name', '=', 'Stock')],
                #     limit=1
                # )
                # if stock_location_ids:
                #     parent_id = stock_location_ids[0]
                #     domain.append(('location_id', '=', parent_id))
            
            location_ids = self._search('stock.location', domain, limit=1)
            
            if location_ids:
                current_location_id = location_ids[0]
                logger.debug(f"Found location '{part}' (ID: {current_location_id})")
            else:
                # Create location
                location_vals = {
                    'name': part,
                    'usage': 'internal',
                }
                
                if parent_id:
                    location_vals['location_id'] = parent_id
                else:
                    # Top level - try to set parent to Stock location
                    stock_location_ids = self._search(
                        'stock.location',
                        [('usage', '=', 'internal'), ('name', '=', 'Stock')],
                        limit=1
                    )
                    if stock_location_ids:
                        location_vals['location_id'] = stock_location_ids[0]
                    else:
                        # If no Stock location found, create without parent (top level)
                        logger.warning(f"No Stock location found, creating '{part}' as top-level location")
                logger.info(f"\n\n{location_vals}")
                if DRY_RUN:
                    logger.info(f"[DRY RUN] Would create location: {location_vals}")
                    # For dry run, simulate the location ID
                    current_location_id = 999999  # Dummy ID for dry run
                else:
                    try:
                        
                        current_location_id = self._create('stock.location', location_vals)
                        logger.info(f"Created location '{part}' (ID: {current_location_id})")
                    except Exception as e:
                        logger.error(f"Failed to create location '{part}': {e}")
                        return None
            
            parent_id = current_location_id
        
        return current_location_id

    def determine_serial_type(self, sheet_name: str) -> str:
        """
        Determine serial_type based on sheet name
        
        Args:
            sheet_name: Sheet name from Excel (e.g., "03071601")
            
        Returns:
            'tuv' or 'setsco'
        """
        if not sheet_name:
            return 'setsco'
        
        sheet_name = str(sheet_name).strip()
        
        # Check if sheet name contains any TUV codes
        for tuv_code in TUV_SHEET_CODES:
            if tuv_code in sheet_name:
                return 'tuv'
        
        return 'setsco'

    def generate_serial_range(self, start: str, end: str) -> List[str]:
        """
        Generate list of serial numbers from start to end
        
        Args:
            start: Start serial number (e.g., "2028901")
            end: End serial number (e.g., "2029699")
            
        Returns:
            List of serial number strings
        """
        if pd.isna(start) or pd.isna(end):
            return []
        
        start = str(start).strip()
        end = str(end).strip()
        
        if not start or not end:
            return []
        
        try:
            # Try to extract prefix and number
            start_match = re.match(r'(.+?)(\d+)$', start)
            end_match = re.match(r'(.+?)(\d+)$', end)
            
            if start_match and end_match:
                start_prefix, start_num_str = start_match.groups()
                end_prefix, end_num_str = end_match.groups()
                
                if start_prefix != end_prefix:
                    logger.warning(
                        f"Start and end serials have different prefixes: "
                        f"'{start}' vs '{end}'. Using numeric range only."
                    )
                    # Fall back to numeric range
                    start_num = int(start)
                    end_num = int(end)
                    num_length = len(str(start_num))
                    
                    serials = []
                    for num in range(start_num, end_num + 1):
                        serials.append(str(num).zfill(num_length))
                    return serials
                
                start_num = int(start_num_str)
                end_num = int(end_num_str)
                num_length = len(start_num_str)
                
                if start_num > end_num:
                    logger.warning(
                        f"Start number ({start_num}) > End number ({end_num}). "
                        f"Skipping range."
                    )
                    return []
                
                serials = []
                for num in range(start_num, end_num + 1):
                    serial_name = f"{start_prefix}{num:0{num_length}d}"
                    serials.append(serial_name)
                
                return serials
            else:
                # Pure numeric range
                start_num = int(start)
                end_num = int(end)
                num_length = len(str(start_num))
                
                if start_num > end_num:
                    logger.warning(
                        f"Start number ({start_num}) > End number ({end_num}). "
                        f"Skipping range."
                    )
                    return []
                
                serials = []
                for num in range(start_num, end_num + 1):
                    serials.append(str(num).zfill(num_length))
                
                return serials
                
        except (ValueError, AttributeError) as e:
            logger.error(f"Error generating serial range from '{start}' to '{end}': {e}")
            return []

    def create_serial_number(self, serial_name: str, setsco_category_id: int,
                            serial_type: str, location_id: Optional[int] = None,
                            category_id: Optional[int] = None,
                            product_id: Optional[int] = None) -> Optional[int]:
        """
        Create a setsco.serial.number record
        
        Args:
            serial_name: Serial number name
            setsco_category_id: Setsco category ID (required)
            serial_type: 'tuv' or 'setsco'
            location_id: Stock location ID (optional)
            category_id: Product category ID (optional)
            product_id: Product ID (optional, linked via Com No)
            
        Returns:
            Serial number ID or None if creation failed
        """
        # Check if serial already exists
        existing_ids = self._search(
            'setsco.serial.number',
            [('name', '=', serial_name)],
            limit=1
        )
        
        if existing_ids:
            logger.debug(f"Serial number '{serial_name}' already exists (ID: {existing_ids[0]})")
            return existing_ids[0]
        
        vals = {
            'name': serial_name,
            'serial_type': serial_type,
            'setsco_category_id': setsco_category_id,
            'state': 'new',
        }
        
        if location_id:
            vals['location_id'] = location_id
        
        if category_id:
            vals['category_id'] = category_id
        
        if product_id:
            vals['product_id'] = product_id
            vals['state'] = 'warehouse'
        else:
            vals['state'] = 'new'
        
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would create serial number: {vals}")
            return None
        
        try:
            serial_id = self._create('setsco.serial.number', vals)
            logger.info(f"Created serial number '{serial_name}' (ID: {serial_id})")
            return serial_id
        except Exception as e:
            logger.error(f"Failed to create serial number '{serial_name}': {e}")
            return None

    def import_from_excel(self, excel_file: str):
        """
        Import serial numbers from Excel file
        
        Args:
            excel_file: Path to Setsco_Combined.xlsx
        """
        logger.info("=" * 80)
        logger.info("Setsco Serial Number Import Started")
        logger.info(f"Excel file: {excel_file}")
        logger.info(f"Dry run: {DRY_RUN}")
        logger.info("=" * 80)
        
        if not Path(excel_file).exists():
            logger.error(f"Excel file not found: {excel_file}")
            return
        
        # Read Excel file
        try:
            df = pd.read_excel(excel_file, sheet_name='Combined')
            logger.info(f"Loaded {len(df)} rows from Excel")
        except Exception as e:
            logger.error(f"Failed to read Excel file: {e}")
            return
        
        # Required columns
        required_cols = ['Start', 'End', 'Location', 'Sheet Name']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            return
        
        # Statistics
        stats = {
            'total_rows': len(df),
            'processed_rows': 0,
            'total_serials_created': 0,
            'total_serials_skipped': 0,
            'errors': 0,
        }
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                logger.info(f"\n--- Processing row {idx + 1}/{len(df)} ---")
                
                # Get values
                start = row.get('Start')
                end = row.get('End')
                location_path = row.get('Location')
                sheet_name = row.get('Sheet Name')
                com_no = row.get('Com No')
                
                logger.info(f"Start: {start}, End: {end}, Location: {location_path}, Sheet: {sheet_name}, Com No: {com_no}")
                
                # Skip if Start or End is missing
                if pd.isna(start) or pd.isna(end):
                    logger.warning(f"Row {idx + 1}: Missing Start or End, skipping")
                    stats['errors'] += 1
                    continue
                
                # Find setsco category
                setsco_category_id = self.find_setsco_category_by_description(sheet_name)
                if not setsco_category_id:
                    logger.warning(f"Row {idx + 1}: No setsco.category found for sheet '{sheet_name}', skipping")
                    stats['errors'] += 1
                    continue
                
                # Determine serial type
                serial_type = self.determine_serial_type(sheet_name)
                logger.info(f"Serial type: {serial_type}")
                
                # Find product by Com No (default_code)
                product_id = None
                if com_no and not pd.isna(com_no):
                    product_id = self.find_product_by_default_code(com_no)
                    if product_id:
                        logger.info(f"Found product with Com No '{com_no}': ID {product_id}")
                    else:
                        logger.warning(f"No product found with Com No '{com_no}', continuing without product link")
                
                # Get or create location
                location_id = self.get_or_create_location(location_path)
                if location_id:
                    logger.info(f"Location ID: {location_id}")

                
                # Generate serial range
                serial_names = self.generate_serial_range(start, end)
                logger.info(f"Generated {len(serial_names)} serial numbers")
                
                if not serial_names:
                    logger.warning(f"Row {idx + 1}: No serial numbers generated, skipping")
                    stats['errors'] += 1
                    continue
                
                # Create serial numbers
                created_count = 0
                skipped_count = 0
                
                for serial_name in serial_names:
                    serial_id = self.create_serial_number(
                        serial_name=serial_name,
                        setsco_category_id=setsco_category_id,
                        serial_type=serial_type,
                        location_id=location_id,
                        category_id=None,  # Can be added later if needed
                        product_id=product_id  # Link product via Com No
                    )
                    
                    if serial_id:
                        created_count += 1
                    else:
                        if not DRY_RUN:
                            skipped_count += 1
                
                stats['processed_rows'] += 1
                stats['total_serials_created'] += created_count
                stats['total_serials_skipped'] += skipped_count
                
                logger.info(
                    f"Row {idx + 1}: Created {created_count} serials, "
                    f"Skipped {skipped_count} serials"
                )
                
            except Exception as e:
                logger.error(f"Error processing row {idx + 1}: {e}", exc_info=True)
                stats['errors'] += 1
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("IMPORT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total rows processed: {stats['processed_rows']}/{stats['total_rows']}")
        logger.info(f"Total serials created: {stats['total_serials_created']}")
        logger.info(f"Total serials skipped: {stats['total_serials_skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("=" * 80)


def main():
    """Main function"""
    # Excel file path - try config first, then default
    try:
        excel_file = script_dir / SETSCO_EXCEL_FILE
    except NameError:
        excel_file = script_dir / 'Setsco_Combined.xlsx'
    
    if not excel_file.exists():
        logger.error(f"Excel file not found: {excel_file}")
        logger.info("Please run combine_setsco_sheets.py first to generate Setsco_Combined.xlsx")
        return 1
    
    try:
        importer = SetscoSerialImporter(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
        importer.import_from_excel(str(excel_file))
        return 0
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

