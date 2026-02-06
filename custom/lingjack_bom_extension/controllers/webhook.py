import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class BOMWebhookController(http.Controller):

    @http.route('/api/bom/search_product', type='http', auth='user', methods=['GET', 'POST'], csrf=False)
    def search_product_bom(self, **kwargs):
        """
        Webhook endpoint to search products and return associated BOMs with extended fields
        
        Parameters:
        - product_name: Product name to search for (partial match supported)
        - product_code: Product default code/reference to search for
        - limit: Maximum number of results to return (default: 20)
        
        Returns JSON with product and BOM information including the extended fields
        """
        try:
            # Get search parameters
            product_name = kwargs.get('product_name', '')
            product_code = kwargs.get('product_code', '')
            limit = int(kwargs.get('limit', 20))
            
            if not product_name and not product_code:
                return self._error_response("Either product_name or product_code must be provided")

            # Build search domain
            domain = []
            if product_name:
                domain.append(('name', 'ilike', product_name))
            if product_code:
                domain.append(('default_code', 'ilike', product_code))
            
            # Search for products
            products = request.env['product.product'].search(domain, limit=limit)

            if not products:
                return self._success_response([], "No products found")
            
            # Get BOMs for found products
            result = []
            for product in products:
                # Search for BOMs with this product
                boms = request.env['mrp.bom'].search([
                    ('product_id', '=', product.id)
                ])
                # If no specific product BOM, search for template BOMs
                if not boms:
                    boms = request.env['mrp.bom'].search([
                        ('product_tmpl_id', '=', product.product_tmpl_id.id),
                        ('product_id', '=', False)
                    ])
                
                product_data = {
                    'product_id': product.id,
                    'product_name': product.name,
                    'product_code': product.default_code or '',
                    'product_template_id': product.product_tmpl_id.id,
                    'boms': []
                }
                
                for bom in boms:
                    bom_data = {
                        'bom_id': bom.id,
                        'bom_reference': bom.code or '',
                        'bom_type': bom.type,
                        'area_id': bom.area_id or '',
                        'sid_prefix': bom.sid_prefix or '',
                        'node_type_id': bom.node_type_id or '',
                        'product_qty': bom.product_qty,
                        'product_uom': bom.product_uom_id.name if bom.product_uom_id else '',
                        'active': bom.active,
                        'components': []
                    }
                    
                    # Add BOM line components
                    for line in bom.bom_line_ids:
                        component_data = {
                            'component_id': line.product_id.id,
                            'component_name': line.product_id.name,
                            'component_code': line.product_id.default_code or '',
                            'product_qty': line.product_qty,
                            'product_uom': line.product_uom_id.name if line.product_uom_id else ''
                        }
                        bom_data['components'].append(component_data)
                    
                    product_data['boms'].append(bom_data)

                result.append(product_data)
            
            return self._success_response(result, f"Found {len(result)} products with BOMs")
            
        except Exception as e:
            _logger.error(f"Error in BOM search webhook: {str(e)}")
            return self._error_response(f"Internal server error: {str(e)}")

    def _success_response(self, data, message="Success"):
        """Helper method to return success response"""
        response = {
            'status': 'success',
            'message': message,
            'data': data
        }
        return request.make_response(
            json.dumps(response, indent=2),
            headers=[('Content-Type', 'application/json')]
        )

    def _error_response(self, error_message):
        """Helper method to return error response"""
        response = {
            'status': 'error',
            'message': error_message,
            'data': []
        }
        return request.make_response(
            json.dumps(response, indent=2),
            headers=[('Content-Type', 'application/json')]
        ) 