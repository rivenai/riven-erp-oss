# -*- coding: utf-8 -*-
"""
Light extensions on account.journal for Mercury-aware behavior.
"""
from odoo import _, api, fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_mercury_journal = fields.Boolean(
        string="Mercury Journal",
        compute='_compute_is_mercury_journal',
        store=True,
        help="True when this journal is linked to a Mercury online account.",
    )

    @api.depends('account_online_link_id.is_mercury')
    def _compute_is_mercury_journal(self):
        for journal in self:
            journal.is_mercury_journal = bool(
                journal.account_online_link_id
                and journal.account_online_link_id.is_mercury
            )

    def fetch_online_sync_favorite_institutions(self):
        """
        Override the GET to OdooFin /get_dashboard_institutions so the
        dashboard ALWAYS shows Mercury as the first option, regardless of
        whether OdooFin's hosted list is reachable.
        """
        result = super().fetch_online_sync_favorite_institutions()
        mercury_entry = {
            'name': 'Mercury Banking',
            'country_code': 'US',
            'is_mercury_native': True,
            'logo': '/mercury_bank_sync/static/description/mercury_logo.png',
        }
        if isinstance(result, list):
            return [mercury_entry] + result
        if isinstance(result, dict) and 'institutions' in result:
            result['institutions'] = [mercury_entry] + result.get('institutions', [])
        return result
