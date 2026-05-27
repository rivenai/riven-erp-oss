# -*- coding: utf-8 -*-
"""
Wizard that replaces the Plaid/OdooFin iframe for Mercury connections.

User flow:
  1. Choose company (defaulted from context)
  2. Paste Mercury API token
  3. Optional: name the workspace ("portlandia-electric-supply", "big-sky-dynamics")
  4. Click "Validate & Connect"
       → calls /accounts to verify the token works
       → stores token in Azure Key Vault
       → creates account.online.link (is_mercury=True)
       → creates one account.online.account per Mercury account
       → next step: assign each account to a journal
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..models.mercury_client import MercuryClient, MercuryAPIError

_logger = logging.getLogger(__name__)


class MercuryConnectWizard(models.TransientModel):
    _name = 'mercury.connect.wizard'
    _description = 'Connect a Mercury Bank workspace to Odoo'

    state = fields.Selection(
        [('input', 'Token Entry'),
         ('validated', 'Token Validated'),
         ('done', 'Accounts Linked')],
        default='input',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company,
    )
    workspace_id = fields.Char(
        string='Mercury Workspace Name',
        help="Optional: e.g. 'portlandia-electric-supply'. Required if your "
             "company holds multiple Mercury orgs (e.g. PES + Big Sky Dynamics).",
    )
    api_token = fields.Char(
        string='Mercury API Token',
        help="Generate at Mercury → Settings → API Tokens. Use a READ-ONLY "
             "token for the initial wiring.",
    )
    account_online_link_id = fields.Many2one(
        'account.online.link', readonly=True,
    )
    discovered_accounts_ids = fields.One2many(
        'mercury.connect.wizard.account', 'wizard_id',
        string='Discovered Accounts', readonly=True,
    )
    error_message = fields.Text(readonly=True)

    # ---------------- token validation ----------------
    def action_validate_token(self):
        """Step 1: ping Mercury, list accounts, store the token in Key Vault."""
        self.ensure_one()
        if not self.api_token or not self.api_token.startswith('secret-token:'):
            raise UserError(_(
                "Mercury tokens start with 'secret-token:' — paste the entire "
                "value Mercury showed you, including the prefix."
            ))

        # 1) Validate by listing accounts
        try:
            client = MercuryClient(token=self.api_token)
            accounts = client.list_accounts()
        except MercuryAPIError as e:
            self.error_message = f'{e.status_code}: {e.body[:300]}'
            raise UserError(_(
                "Mercury rejected the token (%(code)s). Double-check that you "
                "copied the entire 'secret-token:...' string and that it has "
                "not been revoked.\n\nDetails: %(body)s"
            ) % {'code': e.status_code, 'body': e.body[:300]})

        if not accounts:
            raise UserError(_(
                "Mercury accepted the token but returned 0 accounts. Verify "
                "the workspace has at least one open account."
            ))

        # 2) Store in Azure Key Vault BEFORE creating the link record (atomic)
        try:
            self.env['mercury.secret.resolver'].sudo().store_mercury_token(
                company_id=self.company_id.id,
                token=self.api_token,
                workspace_id=self.workspace_id,
            )
        except UserError:
            raise
        except Exception as e:
            _logger.exception('mercury_bank_sync: KV store failed')
            raise UserError(_(
                "Token validated but could not be stored in Azure Key Vault: "
                "%s\n\nFix the Key Vault configuration before retrying — "
                "we never store Mercury tokens in the Odoo database."
            ) % e)

        # 3) Create or update the account.online.link
        link = self.account_online_link_id or self.env['account.online.link'].sudo().create({
            'name': f'Mercury — {self.workspace_id or self.company_id.name}',
            'company_id': self.company_id.id,
            'is_mercury': True,
            'mercury_workspace_id': self.workspace_id or False,
            'provider_type': 'mercury',
            'state': 'connected',
            'auto_sync': True,
        })

        # 4) Create discovered-account preview rows for the wizard
        link_account_model = self.env['account.online.account'].sudo()
        discovered = self.env['mercury.connect.wizard.account'].sudo()
        for acct in accounts:
            existing = link_account_model.search([
                ('online_identifier', '=', acct['id']),
                ('account_online_link_id', '=', link.id),
            ], limit=1)
            if not existing:
                existing = link_account_model.create({
                    'name': acct.get('name') or acct.get('nickname') or 'Mercury Account',
                    'online_identifier': acct['id'],
                    'account_number': acct.get('accountNumber'),
                    'balance': acct.get('currentBalance', 0.0),
                    'available_balance': acct.get('availableBalance',
                                                  acct.get('currentBalance', 0.0)),
                    'account_online_link_id': link.id,
                    'inverse_balance_sign': acct.get('kind') in (
                        'mercuryCredit', 'creditCard', 'IOAccount'),
                    'inverse_transaction_sign': acct.get('kind') in (
                        'mercuryCredit', 'creditCard', 'IOAccount'),
                })
            discovered.create({
                'wizard_id': self.id,
                'online_account_id': existing.id,
                'mercury_kind': acct.get('kind') or 'checking',
                'last4': (acct.get('accountNumber') or '')[-4:],
                'balance': acct.get('currentBalance', 0.0),
            })

        # 5) Stamp the wizard
        self.write({
            'account_online_link_id': link.id,
            'state': 'validated',
            'api_token': '••••••••',  # blank out — token is now in KV
            'error_message': False,
        })
        return self._reopen()

    def action_create_journals(self):
        """Step 2: create one account.journal per discovered account (if missing)."""
        self.ensure_one()
        Journal = self.env['account.journal'].sudo()
        for row in self.discovered_accounts_ids:
            if not row.create_journal:
                continue
            acct = row.online_account_id
            existing_journal = Journal.search([
                ('account_online_account_id', '=', acct.id),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if existing_journal:
                continue
            code = (row.last4 or acct.online_identifier[-4:]).upper()
            Journal.create({
                'name': f'MERCURY-{code}-{acct.name[:24]}',
                'code': f'M{code}'[:5],
                'type': 'bank',
                'company_id': self.company_id.id,
                'currency_id': self.env.ref('base.USD').id,
                'bank_statements_source': 'online_sync',
                'account_online_account_id': acct.id,
                'account_online_link_id': self.account_online_link_id.id,
            })
        self.state = 'done'
        return self._reopen()

    def action_done(self):
        return {'type': 'ir.actions.act_window_close'}

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mercury.connect.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MercuryConnectWizardAccount(models.TransientModel):
    _name = 'mercury.connect.wizard.account'
    _description = 'Per-account row in the Mercury connect wizard'

    wizard_id = fields.Many2one('mercury.connect.wizard', required=True, ondelete='cascade')
    online_account_id = fields.Many2one('account.online.account', required=True, ondelete='cascade')
    name = fields.Char(related='online_account_id.name')
    last4 = fields.Char(string='Last 4', readonly=True)
    mercury_kind = fields.Char(string='Type', readonly=True)
    balance = fields.Float(string='Balance', readonly=True)
    create_journal = fields.Boolean(default=True, string='Create Journal')
