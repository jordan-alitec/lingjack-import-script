# LJ Barcode Qty Demand

## Overview
This module overrides barcode quantity demand using actual reserve quantity and enables PWO QR code scanning to open SFP distribution forms.

## Features

### 1. Barcode Quantity Demand Override
- Adds `actual_reserve_qty` field to `stock.move.line`
- Makes barcode app use actual reserve quantity as qtyDemand
- Handles production-related pickings with actual requested quantities

### 2. PWO QR Code Scanning for SFP Transfer Notes
- **New Feature**: When scanning a PWO QR code (format: `mo:PWO25-04-00001`), the system will:
  - Find Store Finished Product (SFP) transfer notes linked to the manufacturing order
  - If SFP transfer notes exist, open them directly
  - If multiple SFP transfers exist, show list view
  - If single SFP transfer exists, open form view
  - If no SFP transfers found, fallback to standard barcode client action

## Technical Implementation

### Controller Enhancement
The `MRPStockSFPPickingBarcode` controller extends the standard MRP barcode functionality:

```python
def _try_open_production(self, barcode):
    """If barcode represents a production order, open the relevant SFP picking"""
    if barcode.startswith('mo:'):
        barcode = barcode.split(':', 1)[1]
        production = request.env['mrp.production'].search([
            ('name', '=', barcode),
        ], limit=1)
        if production:
            # Find SFP transfer notes linked to this production order
            sfp_pickings = request.env['stock.picking'].search([
                ('mrp_production_id', '=', production.id),
                ('picking_type_id.code', '=', 'internal'),  # SFP transfers are internal
                ('state', 'in', ['draft', 'waiting', 'confirmed', 'assigned'])
            ])
            
            if sfp_pickings:
                # If multiple SFP pickings, show list view
                if len(sfp_pickings) > 1:
                    action = {
                        'type': 'ir.actions.act_window',
                        'name': f'SFP Transfers - {production.name}',
                        'res_model': 'stock.picking',
                        'view_mode': 'list,form',
                        'domain': [('id', 'in', sfp_pickings.ids)],
                        'context': {'default_mrp_production_id': production.id},
                    }
                else:
                    # Single SFP picking, open form view
                    action = {
                        'type': 'ir.actions.act_window',
                        'name': f'SFP Transfer - {production.name}',
                        'res_model': 'stock.picking',
                        'res_id': sfp_pickings.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }
                return {'action': action}
            else:
                # Fallback to standard barcode client action if no SFP pickings found
                action = production.action_open_barcode_client_action()
                return {'action': action}
    return False
```

### Dependencies
- `stock_barcode`: Core barcode functionality
- `lingjack_shop_floor`: Manufacturing order enhancements
- `lingjack_sale_workorder`: SFP distribution functionality

## Usage

### PWO QR Code Scanning
1. **Generate PWO QR Code**: Manufacturing orders with PWO naming convention (e.g., `PWO25-04-00001`)
2. **Scan QR Code**: Use the barcode scanner in the MRP module
3. **Automatic Detection**: System finds SFP transfer notes linked to the manufacturing order
4. **Open SFP Transfer**: If SFP transfer notes exist, opens them directly
5. **Multiple Transfers**: If multiple SFP transfers exist, shows list view
6. **Single Transfer**: If single SFP transfer exists, opens form view
7. **Fallback**: If no SFP transfers found, opens standard manufacturing order barcode interface

### QR Code Format
The QR code should contain the manufacturing order name in the format:
```
mo:PWO25-04-00001
```

Where:
- `mo:` is the prefix indicating manufacturing order
- `PWO25-04-00001` is the actual manufacturing order name

## Testing

### Manual Testing Steps
1. **Create Manufacturing Order**: Create a MO with PWO naming convention
2. **Create SFP Transfer Notes**: Ensure the MO has SFP transfer notes linked via `mrp_production_id`
3. **Generate QR Code**: Create QR code with format `mo:PWO25-04-00001`
4. **Test Scanning**: Use barcode scanner to scan the QR code
5. **Verify Behavior**: Confirm SFP transfer notes open

### Test Scenarios
1. **With SFP Transfer Notes**: QR code should open SFP transfer notes
2. **Multiple SFP Transfers**: QR code should show list view of all SFP transfers
3. **Single SFP Transfer**: QR code should open single SFP transfer form
4. **Without SFP Transfer Notes**: QR code should open standard MO barcode interface
5. **Invalid MO Name**: Should return False (no action)
6. **Malformed QR Code**: Should return False (no action)

## Version History
- **18.0.1.0.3**: Added PWO QR code scanning for SFP transfer notes
- **18.0.1.0.2**: Initial version with barcode qty demand override

## Author
Your Company

## License
LGPL-3
