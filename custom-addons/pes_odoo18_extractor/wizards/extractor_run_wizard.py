# -*- coding: utf-8 -*-
"""One-click wizard to launch a new extraction run."""
from odoo import _, api, fields, models


class ExtractorRunWizard(models.TransientModel):
    _name = 'pes.extractor.run.wizard'
    _description = 'Launch Odoo 18 Extraction Run'

    pull_partners = fields.Boolean(default=True)
    pull_products = fields.Boolean(default=True)
    pull_sale_orders = fields.Boolean(default=True)
    pull_invoices = fields.Boolean(default=True)
    pull_payments = fields.Boolean(default=True)
    cutoff_date = fields.Date(
        help="If set, only records with write_date >= this date are pulled. "
             "Leave empty for full backfill (recommended for first run).",
    )

    def action_launch(self):
        run = self.env['pes.extraction.run'].create({
            'pull_partners': self.pull_partners,
            'pull_products': self.pull_products,
            'pull_sale_orders': self.pull_sale_orders,
            'pull_invoices': self.pull_invoices,
            'pull_payments': self.pull_payments,
            'cutoff_date': self.cutoff_date,
        })
        run.action_run()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pes.extraction.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }
