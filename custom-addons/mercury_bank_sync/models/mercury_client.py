# -*- coding: utf-8 -*-
"""
Thin Mercury Bank REST API client.

Docs: https://docs.mercury.com/reference
Base URL: https://api.mercury.com/api/v1
Auth: Bearer token (read-only or read-write, set per token in Mercury Settings)
Rate limit: ~1 req/sec, soft. We back off on 429.
"""
import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

MERCURY_BASE = 'https://api.mercury.com/api/v1'
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 500  # Mercury max
USER_AGENT = 'odoo-mercury-sync/1.0 (+https://cassilly.capital)'


class MercuryAPIError(Exception):
    """Raised on non-2xx Mercury API responses."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body
        super().__init__(f'Mercury API error {status_code}: {body!r}')


class MercuryClient:
    """
    Stateless wrapper. Instantiate per-request with a token.

    Usage:
        client = MercuryClient(token='secret-token:mercury_production_xxx')
        accounts = client.list_accounts()
        txns = client.list_transactions(account_id, start='2026-01-01')
    """

    def __init__(self, token, timeout=DEFAULT_TIMEOUT):
        if not token:
            raise UserError(_('Mercury API token is required.'))
        self._token = token
        self._timeout = timeout
        self._session = self._build_session()

    # ---------- public API ----------

    def list_accounts(self):
        """GET /accounts → list of account dicts."""
        resp = self._get('/accounts')
        return resp.get('accounts', [])

    def get_account(self, account_id):
        """GET /account/{id} → single account dict."""
        return self._get(f'/account/{account_id}')

    def list_transactions(self, account_id, start=None, end=None,
                          status='sent', search=None, limit=None):
        """
        GET /account/{id}/transactions with full pagination.

        :param str account_id: Mercury account ID
        :param str start: ISO date "YYYY-MM-DD"
        :param str end: ISO date "YYYY-MM-DD"
        :param str status: 'sent' | 'pending' | 'cancelled' | 'failed'
        :param str search: full-text filter
        :param int limit: hard cap on returned rows (None = all)
        :return: list of transaction dicts in chronological order.
        """
        all_txns = []
        offset = 0
        page_size = DEFAULT_PAGE_SIZE
        while True:
            params = {
                'limit': page_size,
                'offset': offset,
                'order': 'asc',
            }
            if start:
                params['start'] = start
            if end:
                params['end'] = end
            if status:
                params['status'] = status
            if search:
                params['search'] = search

            resp = self._get(f'/account/{account_id}/transactions', params=params)
            page = resp.get('transactions', [])
            all_txns.extend(page)

            if limit and len(all_txns) >= limit:
                return all_txns[:limit]

            if len(page) < page_size:
                break
            offset += page_size
            time.sleep(0.2)  # be polite to rate limit
        return all_txns

    def get_statements(self, account_id, start=None, end=None):
        """GET /account/{id}/statements → list of statement metadata."""
        params = {}
        if start:
            params['start'] = start
        if end:
            params['end'] = end
        resp = self._get(f'/account/{account_id}/statements', params=params)
        return resp.get('statements', [])

    def list_recipients(self):
        """GET /recipients → list of saved payees (read-only token can read these)."""
        return self._get('/recipients').get('recipients', [])

    def ping(self):
        """Validate the token by hitting /accounts. Returns True/False."""
        try:
            self._get('/accounts')
            return True
        except MercuryAPIError:
            return False

    # ---------- internal ----------

    def _build_session(self):
        s = requests.Session()
        s.headers.update({
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/json',
            'User-Agent': USER_AGENT,
        })
        retry = Retry(
            total=5,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET']),
            respect_retry_after_header=True,
        )
        s.mount('https://', HTTPAdapter(max_retries=retry))
        return s

    def _get(self, path, params=None):
        url = f'{MERCURY_BASE}{path}'
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            _logger.error('mercury_bank_sync: GET %s failed: %s', path, e)
            raise UserError(_(
                'Network error contacting Mercury: %s. Check VM outbound to '
                'api.mercury.com.'
            ) % e)
        if resp.status_code >= 400:
            body = resp.text[:1000]
            _logger.warning(
                'mercury_bank_sync: %s returned %s — %s',
                path, resp.status_code, body,
            )
            raise MercuryAPIError(resp.status_code, body)
        return resp.json()
