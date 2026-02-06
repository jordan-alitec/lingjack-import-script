# Stock Landed Cost Tier Validation

## Overview

This module extends the functionality of Stock Landed Costs in Odoo to support a tier validation process. It allows administrators to set up approval workflows for landed cost adjustments before they are posted to the system.

## Features

- **Tier-based Approval Workflow**: Configure multiple levels of approval for stock landed costs
- **Search Filters**: "Needs my Review" and "Validated" filters for easy management
- **Status Badge**: Visual validation status indicators in list view
- **Standard Integration**: Uses base tier validation framework

## Configuration

1. Go to **Settings > Technical > Tier Validation > Tier Definitions**
2. Create a new tier definition:
   - **Model**: Select "Stock Landed Cost" (stock.landed.cost)
   - **Review Type**: Choose between individual user, group, or field-based reviewers
   - **Sequence**: Set the order of approval tiers
   - **Domain**: Optionally set conditions for when this tier applies

## Usage

### For Users Creating Landed Costs

1. Create a stock landed cost as usual
2. If tier validation is configured, the system will automatically check validation requirements
3. Use standard tier validation buttons provided by the base framework

### For Reviewers

1. Use **"Needs my Review"** filter to find landed costs requiring your review
2. Review the details and costs
3. Use tier validation buttons to approve or reject

## Technical Details

### Model Extensions

- **stock.landed.cost**: Inherits from `tier.validation` abstract model
- **State Flow**: Validation occurs between `draft` → `posted` states
- **tier.definition**: Extended to include stock.landed.cost in available models

### Integration Points

- **Search Filters**: Adds review filters to search view
- **Tree View**: Adds validation status badge with color coding
- **Base Framework**: Leverages standard tier validation functionality

## Dependencies

- `stock_landed_costs`: Core Odoo landed cost functionality
- `base_tier_validation`: OCA base tier validation framework

## Author

- Alitec Pte. Ltd.
- ForgeFlow S.L.
- Odoo Community Association (OCA)

## License

AGPL-3.0 or later
