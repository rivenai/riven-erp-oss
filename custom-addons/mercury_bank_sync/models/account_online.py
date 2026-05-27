# -*- coding: utf-8 -*-
"""
Hijack of `account.online.link._fetch_odoo_fin`.

The native Odoo 19 Enterprise module `account_online_synchronization` calls
`_fetch_odoo_fin(url, data, ignore_status)` as the SINGLE entry point for all
external bank API traffic. Every endpoint (`/proxy/v1/accounts`,
`/proxy/v2/transactions/posted`, `/proxy/v2/connection_status`, etc.) flows
through that one method.

By overriding it on connections flagged `is_mercury=True`, we redirect those
calls to Mercury's REST API and translate the response shape so all downstream
code (cron, statement-line creation, dedup, dashboard, reconciliation widget)
works without modification.

OdooFin response contract (what the parent expects back):
    {
      'success': bool,                # global ok flag
      'data':    Any,                 # endpoint-specific payload
      'mode':    str,                 # for callbacks: 'link' / 'updateCredentials' / etc
      'message': str,                 # optional user-facing message
      'currency_code': str,           # optional currency
    }
"""
import json
import logging
from datetime import datetime, date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .mercury_client import MercuryClient, MercuryAPIError

_logger = logging.getLogger(__name__)

# Provider type marker stored on account.online.link.provider_type
MERCURY_PROVIDER = 'mercury'


class AccountOnlineLink(models.Model):
    _inherit = 'account.online.link'

    is_mercury = fields.Boolean(
        string="Mercury Connection",
        default=False,
        help="If checked, this connection bypasses the OdooFin proxy and "
             "calls the Mercury Bank REST API directly.",
    )
    mercury_workspace_id = fields.Char(
        string="Mercury Workspace",
        help="Mercury org/workspace identifier — e.g. 'portlandia-electric-supply' "
             "or 'big-sky-dynamics'. Used to disambiguate when one company holds "
             "multiple Mercury orgs.",
    )
    mercury_last_error = fields.Text(
        string="Last Mercury Error",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Hijack point: the single proxy entry method
    # ------------------------------------------------------------------
    def _fetch_odoo_fin(self, url, data=None, ignore_status=False):
        """
        Override of the OdooFin proxy call.

        For non-Mercury links, defers to super(). For Mercury links, routes
        the call to the Mercury API based on URL pattern.
        """
        self.ensure_one()
        if not self.is_mercury:
            return super()._fetch_odoo_fin(
                url, data=data, ignore_status=ignore_status,
            )

        data = data or {}
        _logger.info('mercury_bank_sync: routing %s for link id=%s', url, self.id)

        try:
            return self._dispatch_mercury(url, data)
        except MercuryAPIError as e:
            self.sudo().write({
                'mercury_last_error': f'{e.status_code}: {e.body[:500]}',
                'state': 'error',
            })
            self._log_information(
                state='error',
                subject=_('Mercury API error'),
                message=str(e),
            )
            if ignore_status:
                return {'success': False, 'message': str(e)}
            raise UserError(_(
                "Mercury API returned %(code)s. Check the API token and "
                "network connectivity to api.mercury.com.\n\nDetails: %(body)s"
            ) % {'code': e.status_code, 'body': e.body[:300]})
        except Exception as e:
            _logger.exception('mercury_bank_sync: unexpected error on %s', url)
            self.sudo().write({'mercury_last_error': str(e)[:500]})
            if ignore_status:
                return {'success': False, 'message': str(e)}
            raise UserError(_('Mercury sync error: %s') % e)

    # ------------------------------------------------------------------
    # URL → Mercury API dispatcher
    # ------------------------------------------------------------------
    def _dispatch_mercury(self, url, data):
        """Route a proxy URL to the right Mercury API call + adapter."""
        client = self._mercury_client()

        # Account discovery
        if '/proxy/v1/accounts' in url:
            return self._mercury_response_accounts(client.list_accounts())

        # Transaction fetch (posted only — pending handled separately)
        if '/proxy/v2/transactions' in url:
            return self._mercury_response_transactions(client, data)

        # Health check
        if '/proxy/v2/connection_status' in url or '/connection_status' in url:
            return {
                'success': True,
                'data': {
                    'odoofin_state': 'connected',
                    'expiring_synchronization_date': False,
                },
            }

        # Featured banks / dashboard institutions
        if '/get_dashboard_institutions' in url:
            return {
                'success': True,
                'data': {'institutions': [
                    {'name': 'Mercury Banking',
                     'country_code': 'US',
                     'logo': '/mercury_bank_sync/static/description/mercury_logo.png'},
                ]},
            }

        # OAuth/proxy-specific endpoints — Mercury uses static API keys, no-op
        if any(p in url for p in (
            '/proxy/v1/get_access_token',
            '/proxy/v1/renew_token',
            '/proxy/v1/delete_user',
            '/proxy/v1/authorize_access',
            '/proxy/v1/exchange_token',
            '/proxy/v1/refresh',
        )):
            return {'success': True, 'data': {}}

        _logger.warning('mercury_bank_sync: unhandled URL %s — returning empty success.', url)
        return {'success': True, 'data': {}}

    # ------------------------------------------------------------------
    # Mercury → OdooFin response adapters
    # ------------------------------------------------------------------
    def _mercury_response_accounts(self, mercury_accounts):
        """Translate Mercury /accounts list → OdooFin accounts contract."""
        accounts = []
        for acct in mercury_accounts:
            # Mercury credit-card accounts have inverse balance/txn signs
            is_credit = acct.get('kind') in ('mercuryCredit', 'creditCard', 'IOAccount')
            accounts.append({
                'online_identifier': acct['id'],
                'name': acct.get('name') or acct.get('nickname') or 'Mercury Account',
                'account_number': acct.get('accountNumber'),
                'balance': acct.get('currentBalance', 0.0),
                'available_balance': acct.get('availableBalance',
                                              acct.get('currentBalance', 0.0)),
                'currency_code': acct.get('currency', 'USD'),
                'inverse_balance_sign': is_credit,
                'inverse_transaction_sign': is_credit,
                # Mercury-specific extras (preserved on account_data for traceability)
                'account_data': {
                    'mercury_kind': acct.get('kind'),
                    'mercury_routing_number': acct.get('routingNumber'),
                    'mercury_status': acct.get('status'),
                    'mercury_legal_business_name': acct.get('legalBusinessName'),
                },
            })
        return {'success': True, 'data': {'accounts': accounts}}

    def _mercury_response_transactions(self, client, data):
        """Translate Mercury /transactions list → OdooFin transactions contract."""
        # `data` from Odoo carries: account_id (online_identifier), start_date, end_date
        online_identifier = (
            data.get('online_identifier')
            or data.get('account_id')
            or self._infer_online_identifier(data)
        )
        if not online_identifier:
            raise UserError(_('No Mercury account identifier provided to /transactions.'))

        start = data.get('start_date') or data.get('start')
        end = data.get('end_date') or data.get('end')
        if isinstance(start, (date, datetime)):
            start = start.strftime('%Y-%m-%d')
        if isinstance(end, (date, datetime)):
            end = end.strftime('%Y-%m-%d')

        raw = client.list_transactions(
            online_identifier, start=start, end=end, status='sent',
        )

        transactions = []
        for t in raw:
            posted = t.get('postedAt') or t.get('createdAt')
            txn_date = posted[:10] if posted else None
            transactions.append({
                'online_identifier': t['id'],
                'date': txn_date,
                'amount': float(t.get('amount', 0.0)),
                'currency_code': 'USD',
                'description': self._build_description(t),
                'partner_name': t.get('counterpartyName') or '',
                'partner_account_number': t.get('counterpartyAccountNumber'),
                'partner_routing_number': t.get('counterpartyRoutingNumber'),
                'transaction_type': t.get('kind'),  # 'externalTransfer', 'incomingMoney', etc.
                'reference': t.get('externalMemo'),
                # Forensic extras: full Mercury payload preserved for the
                # dimension rule engine. Stored as JSON on the statement line
                # via the bank_statement_line.create() hook.
                'mercury_raw_payload': json.dumps(t, default=str),
                'mercury_transaction_id': t['id'],
            })

        return {
            'success': True,
            'data': {
                'transactions': transactions,
                'pendings': [],
                'currency_code': 'USD',
            },
        }

    def _build_description(self, txn):
        """Compose the cleanest possible memo line from Mercury's overlapping fields."""
        parts = []
        if txn.get('counterpartyName'):
            parts.append(txn['counterpartyName'])
        if txn.get('externalMemo'):
            parts.append(txn['externalMemo'])
        elif txn.get('bankDescription'):
            parts.append(txn['bankDescription'])
        if txn.get('note'):
            parts.append(f"({txn['note']})")
        return ' — '.join(parts) or txn.get('kind', 'Mercury transaction')

    def _infer_online_identifier(self, data):
        """If the parent didn't pass account_id, try to derive it from the link."""
        if len(self.account_online_account_ids) == 1:
            return self.account_online_account_ids.online_identifier
        return None

    # ------------------------------------------------------------------
    # Mercury client factory
    # ------------------------------------------------------------------
    def _mercury_client(self):
        """Return a configured MercuryClient using the company's stored token."""
        self.ensure_one()
        token = self.env['mercury.secret.resolver'].sudo().get_mercury_token(
            company_id=self.company_id.id,
            workspace_id=self.mercury_workspace_id,
        )
        return MercuryClient(token=token)

    # ------------------------------------------------------------------
    # User-facing actions
    # ------------------------------------------------------------------
    def action_open_mercury_wizard(self):
        """Open the token-paste wizard in place of the OdooFin iframe."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connect Mercury'),
            'res_model': 'mercury.connect.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_company_id': self.company_id.id,
                'default_account_online_link_id': self.id,
            },
        }

    def action_test_mercury_connection(self):
        """Ping Mercury to verify token + connectivity."""
        self.ensure_one()
        if not self.is_mercury:
            raise UserError(_('This is not a Mercury connection.'))
        client = self._mercury_client()
        if client.ping():
            self.sudo().write({'mercury_last_error': False, 'state': 'connected'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mercury'),
                    'message': _('Connection OK — token is valid.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        raise UserError(_(
            'Mercury ping failed. Check the API token in Azure Key Vault.'
        ))
