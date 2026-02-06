# LingJack Shop Floor Module

## Overview
The LingJack Shop Floor module is a specialized Odoo 18 application designed to enhance manufacturing operations by providing comprehensive shop floor management capabilities. This module focuses on employee time tracking, production quantity management, and quality control in manufacturing work orders.

## Features

### 1. Work Order Management
- **Work Order Tracking**: Enhanced work order management with detailed production tracking
- **Real-time Production Monitoring**: Track production progress and quality metrics in real-time
- **Integration**: Seamless integration with MRP work orders and work centers

### 2. Production Quantity Tracking
- **Quantity Management**:
  - Track total produced quantities
  - Monitor qualified products
  - Record and manage defect quantities
  - Calculate net production (total produced - defects)

### 3. Quality Control
- **Quality Checks**: Mandatory quality check confirmation before saving production quantities
- **Defect Tracking**: Detailed tracking of defective items with reasons
- **Validation Rules**:
  - Prevents negative quantities
  - Ensures defect quantities don't exceed production quantities
  - Validates quality checks before session completion

### 4. Employee Time Tracking
- **Work Sessions**: 
  - Start/stop time tracking
  - Session notes and documentation
  - Productivity metrics
- **Employee Assignment**: Link production records to specific employees

### 5. User Interface
- **Touch-friendly Interface**: Optimized for shop floor use
- **Pop-up Forms**: Easy data entry through intuitive pop-up forms
- **Custom CSS and JS**: Enhanced user experience with custom styling and widgets

## Technical Details

### Models

#### 1. MRP Work Order (mrp.workorder)
```python
Fields:
- qty_produced: Float - Qualified production quantity
- total_produced: Float - Total production quantity
- qty_defects: Float - Quantity of defective items
```

#### 2. Work Center Productivity (mrp.workcenter.productivity)
```python
Fields:
- quantity_produced: Float - Production quantity per session
- qty_qualified: Float - Qualified quantity (produced - defects)
- qty_defects: Float - Defect quantity per session
- notes: Text - Production session notes
```

#### 3. Shop Floor Quantity Popup (shop.floor.quantity.popup)
```python
Fields:
- productivity_id: Many2one - Link to productivity record
- workorder_id: Many2one - Related work order
- employee_id: Many2one - Associated employee
- product_id: Many2one - Product being produced
- quantity_produced: Float - Production quantity
- qty_defects: Float - Defect quantity
- notes: Text - Production notes
- quality_check: Boolean - Quality check confirmation
```

### Key Functions

#### Work Order Management
```python
def _compute_qualified_quantities(self):
    """
    Computes total qualified quantities and defects from time tracking
    - Calculates total produced quantity
    - Tracks defect quantities
    - Computes net qualified production
    """
```

#### Productivity Tracking
```python
def _compute_qualified_quantity(self):
    """
    Computes qualified quantity (produced - defects)
    - Ensures non-negative results
    - Updates related work order quantities
    """
```

#### Quality Control
```python
def _check_quantities(self):
    """
    Validates production quantities:
    - No negative quantities
    - Defects cannot exceed production
    - Raises ValidationError for invalid entries
    """
```

### Dependencies
- base
- hr
- mail
- mrp
- mrp_workorder
- lingjack_operation

### Security
- Custom security groups and access rights
- Record rules for data access control

### Views and Assets
- Custom work order views
- Shop floor quantity pop-up forms
- Custom CSS for shop floor interface
- JavaScript widgets for enhanced functionality

## Installation

1. Install required dependencies
2. Copy module to Odoo addons directory
3. Update Odoo apps list
4. Install the module through Odoo apps interface

## Configuration

1. Set up employee records
2. Configure work centers
3. Set up manufacturing operations
4. Assign appropriate user access rights

## Usage

1. Create manufacturing orders
2. Start work order sessions
3. Record production quantities through pop-up interface
4. Complete quality checks
5. Monitor production progress through work order views

## Maintenance Notes

### Common Issues
- Ensure proper employee setup before starting sessions
- Validate quality checks before saving quantities
- Monitor defect ratios for quality control

### Future Enhancements
- Additional quality control metrics
- Enhanced reporting capabilities
- Mobile interface optimization
- Integration with quality control module

## Version Information
- Version: 18.0.1.0.0
- License: LGPL-3
- Author: Alitec Pte Ltd 