from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class DistributionRecordWizard(models.TransientModel):
    _name = 'distribution.record.wizard'
    _description = 'Distribution Record Generation Wizard'

    date_from = fields.Date(string='Invoice Date From', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Invoice Date To', required=True, default=fields.Date.today)
    category_id = fields.Many2one('product.category', string='Product Category', 
                                  help='Filter by product category (optional)', required=False)
    
    # Type filtering
    serial_type = fields.Selection([
        ('both', 'Both TUV & Setsco'),
        ('tuv', 'TUV Only'),
        ('setsco', 'Setsco Only')
    ], string='Serial Type Filter', required=True, default='both',
       help='Filter by serial type: TUV, Setsco, or both')
    
    # Settings selection
    settings_id = fields.Many2one('distribution.settings', string='Distribution Settings', 
                                  required=True, domain="[('company_id', '=', company_id), ('active', '=', True)]")
    company_id = fields.Many2one('res.company', string='Company', 
                                 default=lambda self: self.env.company, readonly=True)
    
    # Settings fields (readonly, for display)
    coc_holder_name = fields.Char(string='CoC Holder Name', readonly=True)
    coc_holder_acra_uen = fields.Char(string='CoC Holder ACRA UEN', readonly=True)
    coc_reference_number = fields.Char(string='CoC Reference Number', readonly=True)
    local_representative_name = fields.Char(string='Local Representative Name', readonly=True)
    local_representative_acra_uen = fields.Char(string='Local Representative ACRA UEN', readonly=True)
    certificate_no = fields.Char(string='Certificate No', readonly=True)
    coc_expired_date = fields.Date(string='CoC Expired Date', readonly=True)
    coc_issue_date = fields.Date(string='CoC Issue Date', readonly=True)
    
    # Export fields
    excel_file = fields.Binary(string='Excel File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Load default settings"""
        res = super().default_get(fields_list)
        # Get the default settings (first sequence, not expired)
        default_settings = self.env['distribution.settings'].get_settings()
        if default_settings:
            res.update({
                'settings_id': default_settings.id,
                'coc_holder_name': default_settings.coc_holder_name,
                'coc_holder_acra_uen': default_settings.coc_holder_acra_uen,
                'coc_reference_number': default_settings.coc_reference_number,
                'local_representative_name': default_settings.local_representative_name,
                'local_representative_acra_uen': default_settings.local_representative_acra_uen,
                'certificate_no': default_settings.certificate_no,
                'coc_expired_date': default_settings.coc_expired_date,
                'coc_issue_date': default_settings.coc_issue_date,
            })
        return res

    @api.onchange('settings_id')
    def _onchange_settings_id(self):
        """Update display fields when settings change"""
        if self.settings_id:
            self.update({
                'coc_holder_name': self.settings_id.coc_holder_name,
                'coc_holder_acra_uen': self.settings_id.coc_holder_acra_uen,
                'coc_reference_number': self.settings_id.coc_reference_number,
                'local_representative_name': self.settings_id.local_representative_name,
                'local_representative_acra_uen': self.settings_id.local_representative_acra_uen,
                'certificate_no': self.settings_id.certificate_no,
                'coc_expired_date': self.settings_id.coc_expired_date,
                'coc_issue_date': self.settings_id.coc_issue_date,
            })

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        """Validate date range"""
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                return {
                    'warning': {
                        'title': _('Invalid Date Range'),
                        'message': _('Date From cannot be later than Date To.')
                    }
                }

    def action_generate_excel(self):
        """Generate Excel file with distribution record"""
        self.ensure_one()
        
        # Validate settings
        if not self.settings_id:
            raise UserError(_('Please select distribution settings.'))
        
        # Validate date range
        if self.date_from > self.date_to:
            raise ValidationError(_('Date From cannot be later than Date To.'))
        
        # Generate Excel file
        excel_data = self._generate_excel_content()
        
        # Create file attachment
        file_name = f'Distribution_Record_{self.date_from}_{self.date_to}.xlsx'
        
        self.write({
            'excel_file': base64.b64encode(excel_data),
            'file_name': file_name
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Record Generated'),
            'res_model': 'distribution.record.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _calculate_column_widths(self, worksheet, headers, data_rows):
        """Calculate optimal column widths based on content length"""
        column_widths = {}
        
        # Set specific widths for certain columns
        column_widths[0] = 20  # Column A: 20
        column_widths[3] = 50  # Column D: 50
        
        # Initialize with header lengths for other columns
        for col_idx, header in enumerate(headers):
            if col_idx not in [0, 3] and header:  # Skip columns A and D
                # Calculate width based on text length (roughly 1.2 characters per unit)
                width = max(len(str(header)) * 1.2, 8)  # Minimum width of 8
                column_widths[col_idx] = width
        
        # Check data rows for longer content (skip columns A and D)
        for row in data_rows:
            for col_idx, value in enumerate(row):
                if col_idx not in [0, 3] and value:  # Skip columns A and D
                    current_width = column_widths.get(col_idx, 8)
                    # Calculate width based on text length
                    text_width = len(str(value)) * 1.2
                    # Add some padding for better readability
                    text_width += 2
                    column_widths[col_idx] = max(current_width, text_width, 8)
        
        # Apply column widths to worksheet
        for col_idx, width in column_widths.items():
            col_letter = chr(65 + col_idx)  # Convert 0->A, 1->B, etc.
            worksheet.set_column(f'{col_letter}:{col_letter}', width)
        
        return column_widths

    def _generate_excel_content(self):
        """Generate Excel content with distribution record format matching the provided template"""
        try:
            import xlsxwriter
            
            # Create Excel file in memory
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            
            # Add formats
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'left',
                'valign': 'vcenter'
            })
            
            header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bg_color': '#F2DCDB'
            })

            title_header_format = workbook.add_format({
                'bold': True,
                'align': 'left',
                'valign': 'vcenter',
                'border': 1,
                'bg_color': '#F2DCDB'
            })
            
            cell_format = workbook.add_format({
                'align': 'left',
                'valign': 'vcenter',
                'border': 1
            })

            cell_format_center = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })

            # Create worksheet
            worksheet = workbook.add_worksheet('Distribution Record')
            
            # Get settings from the selected record
            settings = self.settings_id
            
            # Define headers for column width calculation
            headers = [
                'S/N',
                'Invoice No.',
                'Quantity (nos)',
                'Serial label number(s)',
                'Date of sale to client\n(dd/mm/yyyy)',
                'Client company name',
                'ACRA UEN',
                "Client's mode of sale, e.g. retail outlet, hardware store, door-to-door, online, etc.",
                'Project Name',
                'Ship To',
                'Brand of extinguisher',
                'Model number',
                'Extinguishing Agent',
                'Fire Rating',
                'Capacity'
            ]
            
            # Get delivery data for the date range
            delivery_data = self._get_delivery_data()

            # Prepare data rows for width calculation
            data_rows = []
            for i, delivery in enumerate(delivery_data, 1):
                data_row = [
                    str(i),  # S/N
                    delivery['delivery_order'],  # Invoice No.
                    str(delivery['quantity']),  # Quantity (nos)
                    delivery['serial_number'],  # Serial label number(s)
                    delivery['date'],  # Date of sale to client
                    delivery['customer'],  # Client company name
                    delivery['customer_acra_uen'],  # ACRA UEN
                    delivery['mode_of_sale'],  # Client's mode of sale
                    delivery['project_name'],  # Project Name
                    delivery['delivery_to'],  # Ship To
                    delivery['brand_name'],  # Brand of extinguisher
                    delivery['model_name'],  # Model number
                    delivery['extinguishing_agent'],  # Extinguishing Agent
                    delivery['fire_rating'],  # Fire Rating
                    delivery['capacity']  # Capacity
                ]
                data_rows.append(data_row)
            
            # Calculate and set column widths
            self._calculate_column_widths(worksheet, headers, data_rows)
            
            # Row 1: Title and Certificate No (A1:P1)
            worksheet.write('A1', f'Distribution Record for {self.category_id.name if self.category_id else "Fire Extinguishers - Powder"}', title_format)
            worksheet.write('P1', f'Certificate No :', title_header_format)
            worksheet.write('Q1', f'{settings.certificate_no}', cell_format)

            # Row 2: CoC holder name and Local representative name (A2:P2)
            worksheet.write('A2', 'CoC holder name', title_header_format)
            worksheet.write('B2', settings.coc_holder_name, cell_format)
            worksheet.write('D2', 'Local representative name (where applicable)', title_header_format)
            worksheet.write('E2', settings.local_representative_name, cell_format)
            worksheet.write('P2', f'COC expired :', title_header_format)
            worksheet.write('Q2', f'{settings.coc_expired_date.strftime("%d/%m/%Y") if settings.coc_expired_date else ""}', cell_format)

            # Row 3: CoC holder ACRA UEN and Local representative ACRA UEN (A3:P3)
            worksheet.write('A3', 'CoC holder ACRA UEN', title_header_format)
            worksheet.write('B3', settings.coc_holder_acra_uen, cell_format)
            worksheet.write('D3', 'Local representative ACRA UEN (where applicable)', title_header_format)
            worksheet.write('E3', settings.local_representative_acra_uen, cell_format)
            worksheet.write('P3', f'Date of Issue : {settings.coc_issue_date.strftime("%d/%m/%Y") if settings.coc_issue_date else ""}', title_header_format)
            worksheet.write('Q3', f'{settings.coc_issue_date.strftime("%d/%m/%Y") if settings.coc_issue_date else ""}', cell_format)

            # Row 4: CoC reference number (A4:P4)
            worksheet.write('A4', 'CoC reference number:', title_header_format)
            worksheet.write('B4', settings.coc_reference_number, cell_format)
            
            # Row 5: Certificate Dates and Report Period
            worksheet.write('A5', 'CoC Issue Date:', title_header_format)
            worksheet.write('B5', settings.coc_issue_date.strftime('%d/%m/%Y') if settings.coc_issue_date else '', cell_format)
            # worksheet.write('C5', 'CoC Expired Date:', header_format)
            # worksheet.write('D5', settings.coc_expired_date.strftime('%d/%m/%Y') if settings.coc_expired_date else '', cell_format)
            # worksheet.write('E5', 'Report Period (Invoice Date):', header_format)
            # worksheet.write('F5', f'{self.date_from.strftime("%d/%m/%Y")} - {self.date_to.strftime("%d/%m/%Y")}', cell_format)
            #
            # Row 6: Extinguisher details
            worksheet.write('G6', 'Extinguisher details', title_format)
            
            # Row 7: Column Headers
            worksheet.write('A7', 'S/N', header_format)
            worksheet.write('B7', 'Invoice No.', header_format)
            worksheet.write('C7', 'Quantity (nos) ', header_format)
            worksheet.write('D7', 'Serial label number(s)', header_format)
            worksheet.write('E7', 'Date of sale to client\n(dd/mm/yyyy)', header_format)
            worksheet.write('F7', 'Client company name', header_format)
            worksheet.write('G7', 'ACRA UEN', header_format)
            worksheet.write('H7', "Client's mode of sale, e.g. retail outlet, hardware store, door-to-door, online, etc.", header_format)
            worksheet.write('I7', 'Project Name ', header_format)
            worksheet.write('J7', 'Ship To ', header_format)
            worksheet.write('K7', 'Brand of extinguisher', header_format)
            worksheet.write('L7', 'Model number', header_format)
            worksheet.write('M7', 'Extinguishing Agent', header_format)
            worksheet.write('N7', 'Fire Rating', header_format)
            worksheet.write('O7', 'Capacity', header_format)
            
            # Add data rows (starting from row 8)
            current_row = 8
            for i, delivery in enumerate(delivery_data, 1):
                worksheet.write(f'A{current_row}', i, cell_format_center)  # S/N
                worksheet.write(f'B{current_row}', delivery['delivery_order'], cell_format)  # Invoice No.
                worksheet.write(f'C{current_row}', delivery['quantity'], cell_format)  # Quantity (nos)
                worksheet.write(f'D{current_row}', delivery['serial_number'], cell_format)  # Serial label number(s)
                worksheet.write(f'E{current_row}', delivery['date'], cell_format)  # Date of sale to client
                worksheet.write(f'F{current_row}', delivery['customer'], cell_format)  # Client company name
                worksheet.write(f'G{current_row}', delivery['customer_acra_uen'], cell_format)  # ACRA UEN
                worksheet.write(f'H{current_row}', delivery['mode_of_sale'], cell_format)  # Client's mode of sale
                worksheet.write(f'I{current_row}', delivery['project_name'], cell_format)  # Project Name
                worksheet.write(f'J{current_row}', delivery['delivery_to'], cell_format)  # Ship To
                worksheet.write(f'K{current_row}', delivery['brand_name'], cell_format)  # Brand of extinguisher
                worksheet.write(f'L{current_row}', delivery['model_name'], cell_format)  # Model number
                
                # Combine extinguishing agent, fire rating, and capacity for merged cell
                extinguishing_info = []
                if delivery['extinguishing_agent']:
                    extinguishing_info.append(delivery['extinguishing_agent'])
                if delivery['fire_rating']:
                    extinguishing_info.append(delivery['fire_rating'])
                if delivery['capacity']:
                    extinguishing_info.append(delivery['capacity'])
                combined_info = ' / '.join(extinguishing_info) if extinguishing_info else ''
                
                # Write combined data to column M and merge M:O
                worksheet.write(f'M{current_row}', combined_info, cell_format)
                worksheet.merge_range(f'M{current_row}:O{current_row}', combined_info, cell_format)
                
                current_row += 1
            
            workbook.close()
            output.seek(0)
            return output.getvalue()
            
        except ImportError:
            raise UserError(_('XlsxWriter library is required. Please install it: pip install xlsxwriter'))
        except Exception as e:
            raise UserError(_('Error generating Excel file: %s') % str(e))

    def _get_delivery_data(self):
        """Get delivery data for the specified date range based on setsco serial numbers and invoice dates"""
        # Build domain for setsco serial numbers
        domain = [
            ('state', '=', 'delivered'),  # Only delivered serials
            ('invoice_id', '!=', False),  # Must have invoice assigned
        ]
        
        # Add category filter if specified
        if self.category_id:
            domain.append(('category_id', '=', self.category_id.id))
        
        # Add type filter
        if self.serial_type == 'tuv':
            domain.append(('serial_type', '=', 'tuv'))
        elif self.serial_type == 'setsco':
            domain.append(('serial_type', '=', 'setsco'))
        # If 'both', no additional filter needed
        
        # Search for setsco serial numbers first
        setsco_serials = self.env['setsco.serial.number'].search(domain, order='name')
        
        # Filter by invoice date range after getting the records
        filtered_serials = []
        for serial in setsco_serials:
            if serial.invoice_id and serial.invoice_id.invoice_date:
                if self.date_from <= serial.invoice_id.invoice_date <= self.date_to:
                    if serial.invoice_id.state in ['posted', 'draft']:
                        filtered_serials.append(serial)
        
        delivery_data = []
        for serial in filtered_serials:
            # Get the delivery picking for this serial
            delivery_picking = serial.picking_id
            if delivery_picking and delivery_picking.partner_id:
                # Get product information
                product = serial.product_id
                product_tmpl = product.product_tmpl_id if product else False
                
                # Get sale order information
                sale_order = delivery_picking.sale_id if delivery_picking.sale_id else False
                
                # Get invoice information
                invoice = serial.invoice_id
                
                # Extract product details from lingjack_operation
                brand_name = product_tmpl.brand_id.name if product_tmpl and product_tmpl.brand_id else ''
                model_name = product_tmpl.product_model_id.name if product_tmpl and product_tmpl.product_model_id else ''
                version_name = product_tmpl.version_id.name if product_tmpl and product_tmpl.version_id else ''
                product_description = product_tmpl.product_description if product_tmpl else ''
                
                # Extract sale order details
                project_name = sale_order.project if sale_order and sale_order.project else ''

                sale_type = sale_order.sale_type_id.name if sale_order and sale_order.sale_type_id else ''
                attention_name = sale_order.attention_id.name if sale_order and sale_order.attention_id else ''
                
                # Ship to logic: if delivery_to exists, use partner address (without name), else use partner name
                ship_to = ''
                if delivery_picking.partner_id:
                    # Get address without name
                    address_parts = []
                    if delivery_picking.partner_id.street:
                        address_parts.append(delivery_picking.partner_id.street)
                    if delivery_picking.partner_id.street2:
                        address_parts.append(delivery_picking.partner_id.street2)
                    if delivery_picking.partner_id.city:
                        address_parts.append(delivery_picking.partner_id.city)
                    if delivery_picking.partner_id.state_id:
                        address_parts.append(delivery_picking.partner_id.state_id.name)
                    if delivery_picking.partner_id.zip:
                        address_parts.append(delivery_picking.partner_id.zip)
                    if delivery_picking.partner_id.country_id:
                        address_parts.append(delivery_picking.partner_id.country_id.name)
                    ship_to = ', '.join(address_parts) if address_parts else ''
                else:
                    ship_to = delivery_picking.partner_id.name if delivery_picking.partner_id else ''
                
                # Extract invoice details
                invoice_remarks = invoice.invoice_remarks if invoice else ''
                certificate_no = invoice.certificate_no if invoice else ''
                vessel_name = invoice.vessel_name if invoice else ''
                container_no = invoice.container_no if invoice else ''
                
                # Get customer information
                customer = delivery_picking.partner_id
                customer_name = customer.name if customer else ''
                customer_acra_uen = customer.l10n_sg_unique_entity_number or ''
                
                # Determine mode of sale from customer category
                mode_of_sale = customer.customer_category_id.name if customer and customer.customer_category_id else ''
                
                # Get extinguishing agent from product tags or description
                extinguishing_agent = product.name
                
                # if product_tmpl and product_tmpl.product_tag_ids:
                #     tag_names = product_tmpl.product_tag_ids.mapped('name')
                #     # Extract extinguishing agent from tags
                #     for tag in tag_names:
                #         if 'powder' in tag.lower() or 'foam' in tag.lower() or 'co2' in tag.lower():
                #             extinguishing_agent = tag
                #             break
                #
                # # If not found in tags, try to extract from description
                # if not extinguishing_agent and product_description:
                #     if 'powder' in product_description.lower():
                #         extinguishing_agent = 'Powder'
                #     elif 'foam' in product_description.lower():
                #         extinguishing_agent = 'Foam'
                #     elif 'co2' in product_description.lower():
                #         extinguishing_agent = 'CO2'
                
                # Get fire rating and capacity directly from product template
                fire_rating = product_tmpl.fire_rating if product_tmpl else ''
                capacity = product_tmpl.capacity if product_tmpl else ''
                
                delivery_data.append({
                    'date': serial.invoice_id.invoice_date.strftime('%d/%m/%Y') if serial.invoice_id.invoice_date else '',
                    'serial_number': serial.name or '',
                    'product_name': product.name if product else '',
                    'customer': customer_name,
                    'customer_acra_uen': customer_acra_uen,
                    'quantity': 1,  # Each serial represents 1 quantity
                    'delivery_order': serial.invoice_number or delivery_picking.name or '',
                    'project_name': project_name,
                    'delivery_to': ship_to,
                    'brand_name': brand_name,
                    'model_name': model_name,
                    'version_name': version_name,
                    'extinguishing_agent': extinguishing_agent,
                    'fire_rating': fire_rating,
                    'capacity': capacity,
                    'mode_of_sale': mode_of_sale,
                    'attention_name': attention_name,
                    'certificate_no': certificate_no,
                    'vessel_name': vessel_name,
                    'container_no': container_no,
                    'invoice_remarks': invoice_remarks,
                })
        
        return delivery_data

    def action_download_excel(self):
        """Download the generated Excel file"""
        self.ensure_one()
        
        if not self.excel_file:
            raise UserError(_('Please generate the Excel file first.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&filename_field=file_name&download=true',
            'target': 'self',
        } 