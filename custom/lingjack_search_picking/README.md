# LingJack Search Picking

## Overview
This module provides a quick search functionality for stock pickings with camera barcode scanning capability. It includes two search methods: search by picking number and search by previous transfer.

## Features
- **Root Menu Application**: Accessible as a top-level menu item
- **Camera Barcode Scanner**: Use mobile camera to scan barcodes
- **Two Search Methods**: 
  - Search by picking number
  - Search by previous transfer
- **Wizard Interface**: Simple popup wizard for searching
- **Direct Navigation**: Opens picking form view when found

## Usage

### Access the Module
1. Click on the "Search Picking" icon in the main Odoo menu
2. Choose one of two options:
   - **Search Picking** - Search by picking number
   - **Search by Previous Transfer** - Search by previous transfer number

### Search by Picking Number

**Manual Search:**
1. Enter the picking number in the search field
2. Click "Search" button
3. If found, picking information will be displayed
4. Click "Open Picking" to view the full picking record

**Barcode Scanning:**
1. Click "Scan Barcode" button
2. Allow camera access when prompted
3. Point camera at the picking barcode
4. The system will automatically search and open the picking record
5. If not found, scanner will display error and restart after 2 seconds

### Search by Previous Transfer

**Manual Search:**
1. Enter the previous transfer number in the search field
2. Click "Search" button
3. If found, transfer information will be displayed
4. Click "Open Transfer" to view the full transfer record

**Barcode Scanning:**
1. Click "Scan Barcode" button
2. Allow camera access when prompted
3. Point camera at the previous transfer barcode
4. The system will automatically search and open the transfer record
5. If not found, scanner will display error and restart after 2 seconds

## Technical Details
- **Odoo Version**: 18.0
- **Dependencies**: base, stock
- **Technology**: Html5Qrcode library (v2.3.8) for camera scanning
- **Model**: picking.search.wizard (TransientModel)

## Installation
1. Copy the module to your Odoo addons directory
2. Update the apps list
3. Install "LingJack Search Picking"

## Author
- **Company**: Alitec Pte Ltd
- **Website**: http://www.alitec.sg
- **Last Update**: 10-OCT-2025

