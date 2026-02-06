# Lingjack BOM Extension

This module extends the MRP Bill of Materials (BOM) functionality with additional fields and webhook capabilities.

## Features

### Extended BOM Fields
- **Area ID**: Area identification code
- **SID Prefix**: System ID prefix
- **Node Type ID**: Node type identification

### Route Management
- **Route Field**: Automatically displays 'Buy', 'Make', or 'Buy / Make' for BOM components
- **Manufacturing Route Identification**: Boolean field on stock routes to identify manufacturing operations
- **Smart Route Detection**: Automatically detects component sourcing based on route configuration

### Views
- **Form View**: New fields are added in a dedicated "Lingjack Extensions" section
- **List View**: New fields are available as optional columns (hidden by default)

### Webhook API

#### Product Search Endpoint
**URL**: `/api/bom/search_product`
**Methods**: GET, POST
**Authentication**: User session required

#### Parameters:
- `product_name`: Product name to search for (partial match supported)
- `product_code`: Product default code/reference to search for
- `limit`: Maximum number of results to return (default: 20)

#### Example Usage:
```bash
# Search by product name
curl -X GET "http://your-odoo-instance.com/api/bom/search_product?product_name=Chair"

# Search by product code
curl -X GET "http://your-odoo-instance.com/api/bom/search_product?product_code=CHAIR001"

# Search with limit
curl -X GET "http://your-odoo-instance.com/api/bom/search_product?product_name=Chair&limit=10"
```

#### Response Format:
```json
{
  "status": "success",
  "message": "Found 1 products with BOMs",
  "data": [
    {
      "product_id": 123,
      "product_name": "Office Chair",
      "product_code": "CHAIR001",
      "product_template_id": 456,
      "boms": [
        {
          "bom_id": 789,
          "bom_reference": "BOM001",
          "bom_version": "1.0",
          "bom_type": "normal",
          "area_id": "AREA001",
          "sid_prefix": "SID001",
          "node_type_id": "NODE001",
          "product_qty": 1.0,
          "product_uom": "Unit(s)",
          "active": true,
          "components": [
            {
              "component_id": 101,
              "component_name": "Chair Base",
              "component_code": "BASE001",
              "product_qty": 1.0,
              "product_uom": "Unit(s)"
            }
          ]
        }
      ]
    }
  ]
}
```

## Installation

1. Copy the module to your Odoo addons directory
2. Update the apps list
3. Install the "Lingjack BOM Extension" module
4. Configure the new fields in your BOMs as needed

## Configuration

### Setting Up Manufacturing Routes

To properly identify manufacturing routes for the BOM route field:

1. Go to **Inventory > Configuration > Routes**
2. For each manufacturing route, check the "Is Manufacture Route" checkbox
3. The BOM line route field will automatically update to show 'Make' for components using these routes

### Default Routes

The module includes default manufacturing routes:
- "Manufacture" - Standard manufacturing route
- "Manufacture (Alternative)" - Alternative manufacturing route

## Dependencies

- base
- mrp
- product
- stock 