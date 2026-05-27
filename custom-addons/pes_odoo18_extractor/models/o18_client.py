# -*- coding: utf-8 -*-
"""
Odoo 18 XML-RPC client — READ-ONLY.

Connects to the legacy Odoo 18 Community instance. Every method is a pure
read. No write/create/unlink methods are exposed.

Credentials resolution order:
  1. Azure Key Vault secret named 'odoo18-{role}-credentials' (JSON):
       {"url": "...", "db": "...", "username": "...", "password": "..."}
     Where {role} is 'reader' (read-only user we provision in Odoo 18).
  2. ir.config_parameter fallback (for dev environments).

Example use:
    client = self.env['pes.o18.client'].sudo().get_client()
    partners = client.search_read(
        'res.partner', [('customer_rank', '>', 0)],
        ['name', 'email', 'vat'], limit=100,
    )
"""
import json
import logging
import xmlrpc.client

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class O18ClientService(models.AbstractModel):
    _name = 'pes.o18.client'
    _description = 'Odoo 18 Read-Only XML-RPC Client'

    @api.model
    def _resolve_credentials(self):
        """Pull Odoo 18 reader credentials from Key Vault, fallback to ICP."""
        # Try Key Vault first
        try:
            resolver = self.env['mercury.secret.resolver'].sudo()
            secret_json = resolver.get_secret_by_name('odoo18-reader-credentials')
            creds = json.loads(secret_json)
            return creds
        except Exception as e:
            _logger.warning('o18_client: Key Vault lookup failed (%s) — falling back to ICP.', e)

        # ICP fallback (dev only)
        ICP = self.env['ir.config_parameter'].sudo()
        url = ICP.get_param('pes_odoo18_extractor.url')
        db = ICP.get_param('pes_odoo18_extractor.db')
        username = ICP.get_param('pes_odoo18_extractor.username')
        password = ICP.get_param('pes_odoo18_extractor.password')
        if not all([url, db, username, password]):
            raise UserError(
                "Odoo 18 credentials not configured. "
                "Set Key Vault secret 'odoo18-reader-credentials' "
                "or ir.config_parameter pes_odoo18_extractor.{url,db,username,password}."
            )
        return {'url': url, 'db': db, 'username': username, 'password': password}

    @api.model
    def get_client(self):
        """Return a connected, authenticated O18Client wrapper."""
        creds = self._resolve_credentials()
        return O18Client(
            url=creds['url'].rstrip('/'),
            db=creds['db'],
            username=creds['username'],
            password=creds['password'],
        )


class O18Client:
    """Lean read-only XML-RPC wrapper for Odoo 18."""

    # Methods we explicitly allow. Anything else raises.
    READ_ONLY_METHODS = frozenset({
        'search', 'search_read', 'search_count', 'read',
        'fields_get', 'name_search',
    })

    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self._password = password
        self._uid = None
        self._common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common', allow_none=True)
        self._object = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object', allow_none=True)

    @property
    def uid(self):
        if self._uid is None:
            self._uid = self._common.authenticate(
                self.db, self.username, self._password, {},
            )
            if not self._uid:
                raise UserError(
                    f"Odoo 18 authentication failed for user '{self.username}' on db '{self.db}'."
                )
        return self._uid

    def _execute(self, model, method, *args, **kwargs):
        if method not in self.READ_ONLY_METHODS:
            raise UserError(
                f"o18_client: method '{method}' is not in the read-only allow-list. "
                f"Only {sorted(self.READ_ONLY_METHODS)} are permitted."
            )
        return self._object.execute_kw(
            self.db, self.uid, self._password,
            model, method, list(args), kwargs,
        )

    def search(self, model, domain, **kwargs):
        return self._execute(model, 'search', domain, **kwargs)

    def search_read(self, model, domain, fields, **kwargs):
        return self._execute(model, 'search_read', domain, fields, **kwargs)

    def search_count(self, model, domain):
        return self._execute(model, 'search_count', domain)

    def read(self, model, ids, fields):
        return self._execute(model, 'read', ids, fields)

    def fields_get(self, model, attributes=None):
        kw = {'attributes': attributes} if attributes else {}
        return self._execute(model, 'fields_get', **kw)

    def ping(self):
        """Quick health check."""
        try:
            return bool(self.uid) and bool(self._common.version())
        except Exception:
            return False
