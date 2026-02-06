# Lingjack Service Module

## Overview
This module extends Odoo 18 with custom functionality for Lingjack Service operations, including QR code generation for service identification.

## Features

### QR Code Generation
- **Menu Item**: "Generate Service QR" under Lingjack Service menu
- **Wizard Interface**: User-friendly form to configure QR code generation
- **Two Generation Modes**:
  - **By Range**: Specify start and end sequence numbers
  - **By Quantity**: Specify start sequence and quantity to generate
- **PDF Report**: Generates a professional PDF report with QR codes arranged in a grid format
- **Sequence Management**: Automatically tracks and updates the last used QR sequence in company settings

### Technical Specifications

#### Models
- **res.company**: Extended with `last_used_qr_sequence` field
- **qr.generation.wizard**: Transient model for QR code generation wizard

#### Views
- **Wizard Form**: Interactive form for QR generation configuration
- **PDF Report**: QWeb template for displaying QR codes in grid format (4 columns, multiple rows)
- **Menu Integration**: New menu item in Lingjack Service section

#### Security
- Access rights configured for Sales Team, Sales Managers, FSM Users, and FSM Managers
- Proper model access controls for all user groups

#### Dependencies
- **Python**: qrcode, Pillow (PIL)
- **Odoo**: industry_fsm, stock, industry_fsm_sale, sales_team, web

## Usage

1. Navigate to **Lingjack Service > Generate Service QR**
2. Choose generation type:
   - **By Range**: Enter start and end sequence numbers
   - **By Quantity**: Enter start sequence and quantity
3. Click "Generate QR Codes"
4. System will:
   - Generate QR codes in format: S[7-digit sequence] (e.g., S0055956)
   - Update company's last used sequence
   - Generate and display PDF report with QR codes in grid format

## QR Code Format
- **Pattern**: S + 7-digit sequence number
- **Example**: S0055956, S0055957, S0055958, etc.
- **Display**: Each QR code is labeled with "SID: [Service ID]"

## Configuration
- **Default Start Sequence**: 555956 (configurable in company settings)
- **QR Code Size**: 120x120 pixels in PDF report
- **Grid Layout**: 4 QR codes per row
- **Page Break**: Avoids breaking QR code rows across pages

## Installation Requirements
Ensure the following Python packages are installed:
```bash
pip install qrcode[pil]
```

## Version
- **Module Version**: 18.0.0.0.5
- **Odoo Version**: 18.0
- **Author**: Alitec Pte Ltd


