# -*- coding: utf-8 -*-
{
    'name': 'Mercury Bank Sync',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Direct Mercury Bank API integration — bypasses OdooFin proxy.',
    'description': """
Mercury Bank Sync
=================

Hijacks Odoo's `account_online_synchronization` module so that connections
flagged as Mercury bypass the OdooFin hosted proxy and call the Mercury REST
API directly from this Odoo instance.

Key behaviors:
  * Adds an `is_mercury` flag and `mercury_workspace_id` on `account.online.link`.
  * Overrides `_fetch_odoo_fin` to route Mercury connections to Mercury's API.
  * Provides a token-paste wizard replacing the OdooFin iframe.
  * Auto-creates `account.online.account` records for every Mercury account.
  * Inherits cron, dedup, statement-line creation, and reconciliation UI from core.

Secrets:
  * The Mercury API token is loaded from Azure Key Vault via the VM's Managed
    Identity. Falls back to a Python-keyring entry if Key Vault is unreachable.
  * Tokens are NEVER stored in the Odoo database in plaintext.

License:
  This module inherits from `account_online_synchronization` (OEEL-1). It does
  not redistribute Odoo Enterprise source.
    """,
    'author': 'Cassilly Capital',
    'website': 'https://cassilly.capital',
    'license': 'OEEL-1',
    'depends': [
        'account_online_synchronization',
        'account_accountant',
    ],
    'external_dependencies': {
        'python': [
            'azure-identity',
            'azure-keyvault-secrets',
            'requests',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/mercury_security.xml',
        'data/mercury_provider_data.xml',
        'data/forensic_dimensions_data.xml',
        'wizards/mercury_connect_wizard_views.xml',
        'views/account_online_link_views.xml',
        'views/account_journal_views.xml',
        'views/forensic_dimensions_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercury_bank_sync/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
