# setsco Serial Number Management

A comprehensive custom serial number system for enhanced traceability and state management in Odoo.

## Overview

This module provides a custom serial number system (setsco Serial Numbers) that works alongside Odoo's standard lot/serial functionality, offering detailed tracking through purchase, manufacturing, and delivery processes.

## Key Features

### Serial Number States
- **New**: Newly created
- **Purchased**: Received from vendors  
- **Warehouse**: Available in warehouse
- **Manufacturing**: In production
- **Delivered**: Sent to customers
- **Returned**: Returned from customers
- **Scrapped**: Discarded

### Core Workflows

#### 1. Purchase Workflow
- Purchase setsco serial numbers from vendors
- Create serial numbers from purchase order lines
- Track vendor and purchase information

#### 2. Manufacturing Workflow  
- Assign setsco serial numbers to manufacturing orders
- Link to Odoo lots/serial numbers
- Track through production process

#### 3. Stock Move Workflow
- Require setsco serial selection for stock moves
- Automatic state updates during transfers
- Complete delivery tracking

## Installation

1. Copy module to Odoo addons directory
2. Update apps list  
3. Install "setsco Serial Number" module

## Usage

### Purchase setsco Serials
1. Create purchase order
2. Check "Purchase setsco Serial Numbers" on lines
3. Enter expected serial numbers
4. Create serial numbers from purchase

### Manufacturing Assignment
1. Create manufacturing order
2. Enable "Requires setsco Serial Numbers"
3. Use assignment wizard to select serials
4. Complete manufacturing

### Stock Operations
1. Create stock picking/delivery
2. Select setsco serial numbers for each move line
3. Validate transfer
4. Serial states update automatically

## Dependencies
- base, purchase, stock, mrp, product

## License
Proprietary - Alitec Pte Ltd 