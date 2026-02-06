# See LICENSE file for full copyright and licensing details.

{
    "name": "just Digital Signature",
    "version": "18.0.0.1",
    "author": "justzxxw",
    "complexity": "easy",
    "depends": ["web"],
    "license": "AGPL-3",
    "category": "Tools",
    "description": """
     This module provides the functionality to store digital signature
     Example can be seen into the User's form view where we have
        added a test field under signature.
    """,
    "summary": """
        Touch screen enable so user can add signature with touch devices.
        Digital signature can be very usefull for documents.
    """,
    "images": ["static/description/Digital_Signature.jpg"],
    "data": [
        "views/users_view.xml"],

    "installable": True,
    "auto_install": False,
    'assets': {
        'web.assets_backend': [
            'just_digital_sign/static/src/js/digital_sign.js',
            'just_digital_sign/static/src/xml/digital_sign.xml'
        ],
    }
}
