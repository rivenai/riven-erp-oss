# -*- coding: utf-8 -*-
"""
Extraction run — every pull from Odoo 18 is a discrete, audited batch.

Each run captures: who triggered it, when, which models, how many records
landed, any errors, and a final state. Staging records carry the run_id
so we can roll back a bad batch by archiving its run.
"""
import logging
import time
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ExtractionRun(models.Model):
    _name = 'pes.extraction.run'
    _description = 'Odoo 18 Extraction Run'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    state = fields.Selection(
        [('draft', 'Draft'),
         ('running', 'Running'),
         ('completed', 'Completed'),
         ('failed', 'Failed'),
         ('archived', 'Archived')],
        default='draft',
        required=True,
        index=True,
    )
    triggered_by_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    duration_seconds = fields.Float(compute='_compute_duration', store=True)

    # Models requested
    pull_partners = fields.Boolean(default=True)
    pull_products = fields.Boolean(default=True)
    pull_sale_orders = fields.Boolean(default=True)
    pull_invoices = fields.Boolean(default=True)
    pull_payments = fields.Boolean(default=True)

    # Optional date filter — pull only records created/modified on/after this date
    cutoff_date = fields.Date(
        help="If set, only records with write_date >= this date are pulled. "
             "Empty = full pull (initial migration)."
    )

    # Counters
    partner_count = fields.Integer(readonly=True)
    product_count = fields.Integer(readonly=True)
    sale_order_count = fields.Integer(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    payment_count = fields.Integer(readonly=True)

    error_log = fields.Text(readonly=True)

    @api.depends('create_date', 'state')
    def _compute_display_name(self):
        for run in self:
            ts = run.create_date and run.create_date.strftime('%Y-%m-%d %H:%M') or 'pending'
            run.display_name = f"O18 Pull · {ts} · {run.state}"

    @api.depends('started_at', 'finished_at')
    def _compute_duration(self):
        for run in self:
            if run.started_at and run.finished_at:
                run.duration_seconds = (
                    run.finished_at - run.started_at
                ).total_seconds()
            else:
                run.duration_seconds = 0.0

    # ------------------------------------------------------------------
    # Run orchestration
    # ------------------------------------------------------------------
    def action_run(self):
        """Execute the configured extraction."""
        self.ensure_one()
        if self.state == 'running':
            raise UserError(_("This run is already in progress."))

        self.write({
            'state': 'running',
            'started_at': fields.Datetime.now(),
            'error_log': False,
        })

        client = self.env['pes.o18.client'].sudo().get_client()
        if not client.ping():
            self._fail("Odoo 18 connection failed (ping returned False).")
            return

        errors = []
        start = time.time()

        try:
            if self.pull_partners:
                self.partner_count = self.env['pes.staging.partner'].sudo().pull_from_o18(
                    client, run=self,
                )
            if self.pull_products:
                self.product_count = self.env['pes.staging.product'].sudo().pull_from_o18(
                    client, run=self,
                )
            if self.pull_sale_orders:
                self.sale_order_count = self.env['pes.staging.sale.order'].sudo().pull_from_o18(
                    client, run=self,
                )
            if self.pull_invoices:
                self.invoice_count = self.env['pes.staging.invoice'].sudo().pull_from_o18(
                    client, run=self,
                )
            if self.pull_payments:
                self.payment_count = self.env['pes.staging.payment'].sudo().pull_from_o18(
                    client, run=self,
                )
        except Exception as e:
            _logger.exception('Extraction run %s failed.', self.id)
            errors.append(str(e))

        elapsed = time.time() - start
        if errors:
            self._fail('\n'.join(errors))
        else:
            self.write({
                'state': 'completed',
                'finished_at': fields.Datetime.now(),
            })
            _logger.info(
                'Extraction run %s completed in %.1fs: '
                'partners=%s products=%s sale_orders=%s invoices=%s payments=%s',
                self.id, elapsed,
                self.partner_count, self.product_count, self.sale_order_count,
                self.invoice_count, self.payment_count,
            )

    def _fail(self, message):
        self.write({
            'state': 'failed',
            'finished_at': fields.Datetime.now(),
            'error_log': message,
        })

    def action_archive_run(self):
        """Archive this run AND all staging records that came from it."""
        self.ensure_one()
        for model in (
            'pes.staging.partner',
            'pes.staging.product',
            'pes.staging.sale.order',
            'pes.staging.invoice',
            'pes.staging.payment',
        ):
            recs = self.env[model].sudo().search([('extraction_run_id', '=', self.id)])
            recs.write({'active': False})
        self.write({'state': 'archived'})
