# -*- coding: utf-8 -*-
"""
Mercury → bank statement line dimension wiring.

When Odoo's online_sync framework creates account.bank.statement.line records
from the Mercury payload, we hook the create() to apply forensic dimension
rules to the resulting move lines.

Mercury raw payload is preserved on the statement line via an extra JSON
field so the rule engine has full context (counterparty, kind, memo, etc.)
even after the OdooFin response shape strips some of it.
"""
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    mercury_raw_payload = fields.Text(
        string="Mercury Raw Payload",
        readonly=True,
        help="Original Mercury transaction JSON for forensic traceability. "
             "Populated only for lines sourced from a Mercury connection.",
    )
    mercury_transaction_id = fields.Char(
        string="Mercury Transaction ID",
        index=True,
        readonly=True,
        help="Mercury's stable txn id. Used for dedup beyond Odoo's online_identifier.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Capture Mercury payload + apply dimension rules at creation."""
        lines = super().create(vals_list)

        # Best-effort dimension tagging. Don't fail line creation if rules error.
        for line in lines:
            try:
                payload = None
                if line.mercury_raw_payload:
                    try:
                        payload = json.loads(line.mercury_raw_payload)
                    except (ValueError, TypeError):
                        payload = None
                # Tag the move lines this statement line will generate.
                # At create() time the move may not yet exist; we tag on
                # the move lines once they're materialized via the post() hook.
                line._pes_tag_pending_payload = payload
            except Exception:
                _logger.exception(
                    'mercury_bank_sync: dimension tagging deferred for line %s',
                    line.id,
                )
        return lines


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """After posting, apply Mercury dimension rules to the resulting lines."""
        res = super().action_post()
        for move in self:
            for line in move.line_ids:
                stmt_line = move.statement_line_id if hasattr(
                    move, 'statement_line_id'
                ) else False
                if stmt_line and stmt_line.mercury_raw_payload:
                    try:
                        payload = json.loads(stmt_line.mercury_raw_payload)
                    except (ValueError, TypeError):
                        payload = None
                    line._pes_apply_dimension_rules(mercury_payload=payload)
                else:
                    line._pes_apply_dimension_rules()
        return res
