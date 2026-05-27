# -*- coding: utf-8 -*-
{
    'name': 'PES Odoo 18 Extractor (Read-Only)',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Read-only extractor pulling Odoo 18 (Community) data into Odoo 19 staging schema — forensic reconciliation source-of-truth.',
    'description': """
PES Odoo 18 Extractor
=====================

Pulls data from the legacy Odoo 18 Community instance at
erp.portlandiaelectric.supply via XML-RPC and lands it in dedicated
staging tables (pes.staging.*) inside this Odoo 19 instance.

CRITICAL CONSTRAINTS:
  * Odoo 18 is READ-ONLY. This module NEVER writes to Odoo 18.
  * Staging data is NEVER auto-posted to live journals. A human review +
    promotion wizard is required.
  * Every staged record carries `o18_model` + `o18_id` for traceability,
    plus a `extraction_run_id` for batch attribution.
  * Connection credentials resolved from Azure Key Vault via the
    existing mercury.secret.resolver service.

What it pulls (Phase 1 manifest):
  * res.partner          — customers, vendors (with manufacturer flag)
  * product.product      — full product catalog with cost/list price
  * sale.order           — closed and open orders (full lines)
  * account.move         — invoices (customer + vendor) with full lines
  * account.payment      — payment history
  * account.move.line    — for AR/AP aging reconciliation
  * res.users            — user list (for change-attribution traceability)

Phase 2 (post-review):
  * stock.picking, stock.move (inventory delta)
  * mrp.production (if present)
  * crm.lead (if pulled forward)

Reconciliation outputs (built on staging):
  * 229 manufacturer relationships scorecard
  * $300K+ vendor credit aging report
  * 65 open Mercury invoices (~$736K) match-up against Odoo 19 + Mercury statements
  * Flores Photovoltaics $21,800 Virginia deal end-to-end walkthrough

License: LGPL-3 (this module is our own, no Enterprise inheritance).
""",
    'author': 'Cassilly Capital',
    'website': 'https://cassilly.capital',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'mercury_bank_sync',  # for shared secret resolver + dimensions
    ],
    'external_dependencies': {
        'python': [
            'requests',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/extractor_config_data.xml',
        'views/extraction_run_views.xml',
        'views/staging_views.xml',
        'wizards/extractor_run_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
