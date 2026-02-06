#!/usr/bin/env python3
"""
Example API calls for Lingjack BOM Extension webhook

This file demonstrates how to call the BOM search webhook from external applications.
"""

import requests
import json
from urllib.parse import urljoin


class BOMWebhookClient:
    """Client for interacting with Lingjack BOM Extension webhook"""
    
    def __init__(self, base_url, username=None, password=None, session_id=None):
        """
        Initialize the client
        
        Args:
            base_url: Base URL of Odoo instance (e.g., 'http://localhost:8069')
            username: Odoo username (optional if using session_id)
            password: Odoo password (optional if using session_id)
            session_id: Existing session ID (optional)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        if session_id:
            self.session.cookies.set('session_id', session_id)
        elif username and password:
            self.login(username, password)
    
    def login(self, username, password):
        """Login to Odoo and get session"""
        login_url = urljoin(self.base_url, '/web/session/authenticate')
        login_data = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {
                'db': 'lingjack',  # Update with your database name
                'login': username,
                'password': password,
            }
        }
        
        response = self.session.post(login_url, json=login_data)
        result = response.json()
        
        if result.get('result', {}).get('uid'):
            print(f"Successfully logged in as user ID: {result['result']['uid']}")
            return True
        else:
            print("Login failed")
            return False
    
    def search_product_bom(self, product_name=None, product_code=None, limit=20):
        """
        Search for products and their BOMs
        
        Args:
            product_name: Product name to search for
            product_code: Product code to search for
            limit: Maximum number of results
            
        Returns:
            dict: API response
        """
        url = urljoin(self.base_url, '/api/bom/search_product')
        
        params = {'limit': limit}
        if product_name:
            params['product_name'] = product_name
        if product_code:
            params['product_code'] = product_code
        
        response = self.session.get(url, params=params)
        
        try:
            return response.json()
        except json.JSONDecodeError:
            return {
                'status': 'error',
                'message': f'Invalid response: {response.text}',
                'data': []
            }


def main():
    """Example usage of the BOM webhook client"""
    
    # Initialize client
    client = BOMWebhookClient(
        base_url='http://localhost:8089',
        username='admin',  # Update with your credentials
        password='admin'   # Update with your credentials
    )
    
    # Example 1: Search by product name
    # print("=== Example 1: Search by product name ===")
    # result = client.search_product_bom(product_name='Screens')
    # print(json.dumps(result, indent=2))
    
    # # Example 2: Search by product code
    # print("\n=== Example 2: Search by product code ===")
    # result = client.search_product_bom(product_code='PROD001')
    # print(json.dumps(result, indent=2))
    #
    # # Example 3: Search with limit
    # print("\n=== Example 3: Search with limit ===")
    # result = client.search_product_bom(product_name='Product', limit=5)
    # print(json.dumps(result, indent=2))
    
    # Example 4: Extract specific BOM information
    print("\n=== Example 4: Extract BOM extension fields ===")
    result = client.search_product_bom(product_name='Bloc', limit=1)
    
    if result.get('status') == 'success' and result.get('data'):
        for product in result['data']:
            print(f"Product: {product['product_name']} ({product['product_code']})")
            for bom in product['boms']:
                print(f"  BOM ID: {bom['bom_id']}")
                print(f"  Area ID: {bom['area_id']}")
                print(f"  SID Prefix: {bom['sid_prefix']}")
                print(f"  Node Type ID: {bom['node_type_id']}")
                print(f"  Components: {len(bom['components'])}")


if __name__ == '__main__':
    main() 