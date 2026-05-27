# -*- coding: utf-8 -*-
"""Staging table for Odoo 18 account.payment records."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StagingPayment(models.Model):
    _name = 'pes.staging.payment'
    _description = 'Staged account.payment from Odoo 18'
    _order = 'payment_date desc'

    extraction_run_id = fields.Many2one(
        'pes.extraction.run', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)

    o18_id = fields.Integer(required=True, index=True)
    o18_model = fields.Char(default='account.payment', readonly=True)
    o18_write_date = fields.Datetime()

    name = fields.Char(index=True)
    state = fields.Char()
    payment_type = fields.Selection(
        [('outbound', 'Outbound'), ('inbound', 'Inbound')],
    )
    partner_o18_id = fields.Integer()
    partner_name = fields.Char()
    payment_date = fields.Date()
    amount = fields.Float(digits=(16, 2))
    currency_code = fields.Char(default='USD')
    journal_name = fields.Char()
    ref = fields.Char()
    payment_method = fields.Char()

    _sql_constraints = [
        ('o18_id_run_uniq',
         'unique(o18_id, extraction_run_id)',
         'Same Odoo 18 payment appears twice in one run.'),
    ]

    @api.model
    def pull_from_o18(self, client, run):
        domain = []
        if run.cutoff_date:
            domain.append(('write_date', '>=', str(run.cutoff_date)))

        rows = client.search_read(
            'account.payment', domain,
            ['name', 'state', 'payment_type', 'partner_id',
             'date', 'amount', 'currency_id', 'journal_id', 'ref',
             'payment_method_id', 'write_date'],
        )
        _logger.info('staging_payment: got %s payments.', len(rows))

        vals_list = [{
            'extraction_run_id': run.id,
            'o18_id': r['id'],
            'o18_write_date': r.get('write_date'),
            'name': r.get('name'),
            'state': r.get('state'),
            'payment_type': r.get('payment_type'),
            'partner_o18_id': r.get('partner_id') and r['partner_id'][0] or False,
            'partner_name': r.get('partner_id') and r['partner_id'][1] or False,
            'payment_date': r.get('date') or False,
            'amount': r.get('amount') or 0.0,
            'currency_code': r.get('currency_id') and r['currency_id'][1] or 'USD',
            'journal_name': r.get('journal_id') and r['journal_id'][1] or False,
            'ref': r.get('ref'),
            'payment_method': r.get('payment_method_id') and r['payment_method_id'][1] or False,
        } for r in rows]

        BATCH = 500
        created = 0
        for i in range(0, len(vals_list), BATCH):
            self.create(vals_list[i:i + BATCH])
            created += len(vals_list[i:i + BATCH])
        return created
