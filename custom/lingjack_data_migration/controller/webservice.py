# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response


class LingjackWebserviceController(http.Controller):
    @http.route('/api/dbname', type='http', auth='public', methods=['GET'], csrf=False)
    def get_dbname(self, **kwargs):
        dbname = request.db or getattr(getattr(request, 'env', None), 'cr', None)
        if hasattr(dbname, 'dbname'):
            dbname = dbname.dbname
        if not isinstance(dbname, str):
            try:
                import odoo
                dbname = odoo.tools.config.get('db_name') or ''
            except Exception:
                dbname = ''
        return Response((dbname or '').encode('utf-8'), content_type='text/plain; charset=utf-8')
