# -*- coding: utf-8 -*-
"""Staging table for Odoo 18 account.move (invoices) + lines."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StagingInvoice(models.Model):
    _name = 'pes.staging.invoice'
    _description = 'Staged account.move (invoice) from Odoo 18'
    _order = 'invoice_date desc'

    extraction_run_id = fields.Many2one(
        'pes.extraction.run', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)

    o18_id = fields.Integer(required=True, index=True)
    o18_model = fields.Char(default='account.move', readonly=True)
    o18_write_date = fields.Datetime()

    name = fields.Char(index=True)
    move_type = fields.Selection(
        [('out_invoice', 'Customer Invoice'),
         ('out_refund', 'Customer Refund'),
         ('in_invoice', 'Vendor Bill'),
         ('in_refund', 'Vendor Refund'),
         ('entry', 'Journal Entry'),
         ('out_receipt', 'Customer Receipt'),
         ('in_receipt', 'Vendor Receipt')],
    )
    state = fields.Char()
    payment_state = fields.Char()
    partner_o18_id = fields.Integer()
    partner_name = fields.Char()
    invoice_date = fields.Date()
    invoice_date_due = fields.Date()
    amount_untaxed = fields.Float(digits=(16, 2))
    amount_tax = fields.Float(digits=(16, 2))
    amount_total = fields.Float(digits=(16, 2))
    amount_residual = fields.Float(digits=(16, 2))
    currency_code = fields.Char(default='USD')
    ref = fields.Char()
    line_ids = fields.One2many('pes.staging.invoice.line', 'invoice_id')

    # Forensic flags
    is_open = fields.Boolean(
        compute='_compute_open',
        store=True,
        help="True for non-zero residual on posted invoices — counts toward "
             "the '65 open Mercury invoices ~$736K' reconciliation target.",
    )

    _sql_constraints = [
        ('o18_id_run_uniq',
         'unique(o18_id, extraction_run_id)',
         'Same Odoo 18 invoice appears twice in one run.'),
    ]

    @api.depends('amount_residual', 'state')
    def _compute_open(self):
        for r in self:
            r.is_open = (r.state == 'posted') and (abs(r.amount_residual or 0) > 0.01)

    @api.model
    def pull_from_o18(self, client, run):
        domain = [('move_type', 'in', [
            'out_invoice', 'out_refund', 'in_invoice', 'in_refund',
        ])]
        if run.cutoff_date:
            domain.append(('write_date', '>=', str(run.cutoff_date)))

        rows = client.search_read(
            'account.move', domain,
            ['name', 'move_type', 'state', 'payment_state', 'partner_id',
             'invoice_date', 'invoice_date_due',
             'amount_untaxed', 'amount_tax', 'amount_total', 'amount_residual',
             'currency_id', 'ref', 'invoice_line_ids', 'write_date'],
        )
        _logger.info('staging_invoice: got %s invoices.', len(rows))

        line_ids = []
        for r in rows:
            line_ids.extend(r.get('invoice_line_ids') or [])

        line_rows = []
        if line_ids:
            line_rows = client.search_read(
                'account.move.line',
                [('id', 'in', line_ids)],
                ['move_id', 'product_id', 'name', 'quantity',
                 'price_unit', 'price_subtotal', 'price_total',
                 'account_id', 'partner_id'],
            )

        lines_by_invoice = {}
        for ln in line_rows:
            mid = ln.get('move_id') and ln['move_id'][0]
            if mid:
                lines_by_invoice.setdefault(mid, []).append(ln)

        created = 0
        for r in rows:
            inv_vals = {
                'extraction_run_id': run.id,
                'o18_id': r['id'],
                'o18_write_date': r.get('write_date'),
                'name': r.get('name'),
                'move_type': r.get('move_type'),
                'state': r.get('state'),
                'payment_state': r.get('payment_state'),
                'partner_o18_id': r.get('partner_id') and r['partner_id'][0] or False,
                'partner_name': r.get('partner_id') and r['partner_id'][1] or False,
                'invoice_date': r.get('invoice_date') or False,
                'invoice_date_due': r.get('invoice_date_due') or False,
                'amount_untaxed': r.get('amount_untaxed') or 0.0,
                'amount_tax': r.get('amount_tax') or 0.0,
                'amount_total': r.get('amount_total') or 0.0,
                'amount_residual': r.get('amount_residual') or 0.0,
                'currency_code': r.get('currency_id') and r['currency_id'][1] or 'USD',
                'ref': r.get('ref'),
                'line_ids': [
                    (0, 0, {
                        'o18_id': ln['id'],
                        'product_o18_id': ln.get('product_id') and ln['product_id'][0] or False,
                        'product_name': ln.get('product_id') and ln['product_id'][1] or False,
                        'description': ln.get('name'),
                        'quantity': ln.get('quantity') or 0.0,
                        'price_unit': ln.get('price_unit') or 0.0,
                        'price_subtotal': ln.get('price_subtotal') or 0.0,
                        'price_total': ln.get('price_total') or 0.0,
                        'account_o18_id': ln.get('account_id') and ln['account_id'][0] or False,
                        'account_name': ln.get('account_id') and ln['account_id'][1] or False,
                    })
                    for ln in lines_by_invoice.get(r['id'], [])
                ],
            }
            self.create(inv_vals)
            created += 1
        return created


class StagingInvoiceLine(models.Model):
    _name = 'pes.staging.invoice.line'
    _description = 'Staged invoice line from Odoo 18'
    _order = 'invoice_id, id'

    invoice_id = fields.Many2one(
        'pes.staging.invoice', required=True, ondelete='cascade', index=True,
    )
    o18_id = fields.Integer(required=True, index=True)
    product_o18_id = fields.Integer()
    product_name = fields.Char()
    description = fields.Text()
    quantity = fields.Float(digits=(16, 4))
    price_unit = fields.Float(digits=(16, 4))
    price_subtotal = fields.Float(digits=(16, 2))
    price_total = fields.Float(digits=(16, 2))
    account_o18_id = fields.Integer()
    account_name = fields.Char()
