# Odoo BoM Import Script

This script imports Bill of Materials (BoM) data from Excel files into Odoo 18's `mrp.bom` model.

## Features

- Reads BoM data from Excel files
- Creates `mrp.bom` records in Odoo
- Creates `mrp.bom.line` records (components) for each BoM
- Validates product references before importing
- Supports dry-run mode for testing
- Comprehensive error handling and logging
- Detailed import statistics

## Prerequisites

1. Python 3.6+
2. Required Python packages:
   ```bash
   pip install openpyxl
   ```
3. Odoo 18 instance with:
   - `mrp` module installed
   - Products already created in the system
   - XML-RPC enabled (default)

## Excel File Format

The script expects an Excel file with the following structure:

| Column | Description | Example |
|--------|-------------|---------|
| 1 (A) | Product Name | [0307418100000] 220MM(W)X510MM(H)X175MM(D)... |
| 5 (E) | Product Reference | 0307418100000 |
| 6 (F) | Component Reference | 0304900000000 |
| 7 (G) | Quantity | 2 |
| 8 (H) | Unit of Measure | nos. |

**Important Notes:**
- When Column A (Product Name) has a value, it indicates a new BoM
- Rows with empty Column A are components of the previous BoM
- The script groups components under their parent BoM automatically

## Setup

1. **Copy the configuration template:**
   ```bash
   cp config_example.py config.py
   ```

2. **Edit `config.py` with your Odoo credentials:**
   ```python
   ODOO_URL = 'http://your-odoo-server:8069'
   ODOO_DB = 'your_database'
   ODOO_USERNAME = 'admin'
   ODOO_PASSWORD = 'your_password'
   EXCEL_FILE = 'split_output.xlsx'
   DRY_RUN = True  # Set to False when ready to import
   ```

3. **Ensure products exist in Odoo:**
   - Products must be created in Odoo before importing BoMs
   - Product references (default_code) must match the Excel file
   - Component products must also exist

## Usage

### Dry Run (Recommended First Step)

Test the import without creating records:

```bash
python3 import_bom_to_odoo.py
```

Or specify a different Excel file:

```bash
python3 import_bom_to_odoo.py path/to/your/file.xlsx
```

### Execute Import

After verifying the dry run results, execute the actual import:

```bash
python3 import_bom_to_odoo.py --execute
```

Or with a specific file:

```bash
python3 import_bom_to_odoo.py path/to/your/file.xlsx --execute
```

## How It Works

1. **Parse Excel File:**
   - Reads the Excel file and identifies BoM headers (rows with Product Name)
   - Groups components under their parent BoM

2. **Validate Products:**
   - Searches for products by reference code (default_code)
   - Skips BoMs/components if products are not found

3. **Create BoM Records:**
   - Creates `mrp.bom` record for each product
   - Links to the product via `product_id`

4. **Create BoM Lines:**
   - Creates `mrp.bom.line` records for each component
   - Sets quantity and unit of measure

5. **Report Statistics:**
   - Shows total BoMs found, created, and skipped
   - Lists any errors encountered

## Troubleshooting

### "Product not found" errors

- Ensure products are created in Odoo before importing
- Verify product reference codes (default_code) match exactly
- Check for leading/trailing spaces in Excel data

### "Authentication failed"

- Verify Odoo URL, database name, username, and password
- Ensure XML-RPC is enabled in Odoo
- Check network connectivity to Odoo server

### "UOM not found" warnings

- The script will use the product's default UOM if specified UOM is not found
- Create missing UOMs in Odoo if needed: Inventory → Configuration → Units of Measure

### Import is slow

- The script processes BoMs sequentially
- For large files, consider splitting into smaller batches
- Check Odoo server performance

## Example Output

```
2024-01-15 10:30:00 - INFO - Successfully connected to Odoo database: mydb
2024-01-15 10:30:01 - INFO - Parsed 50 BoMs from Excel file
2024-01-15 10:30:02 - INFO - Created BoM ID 123 for product ID 456
...

============================================================
IMPORT STATISTICS
============================================================
Total BoMs found: 50
BoMs created: 48
BoMs skipped: 2
Total lines found: 250
Lines created: 245
Lines skipped: 5
Errors: 7
============================================================
```

## Notes

- The script uses Odoo's XML-RPC API, which is the standard way to interact with Odoo programmatically
- BoM type is set to 'normal' by default (can be modified in the script)
- The script handles missing UOMs gracefully by using product defaults
- All operations are logged for debugging purposes

## Support

For issues or questions:
1. Check the error messages in the output
2. Review Odoo logs for server-side errors
3. Verify Excel file format matches expected structure
4. Ensure all products exist in Odoo before importing










