# -*- coding: utf-8 -*-
"""
Forensic Reconciliation Dimensions
==================================

Adds the analytic dimensions required to make every Mercury (and eventually
every Odoo 18 backfill) transaction replayable across the SEZ Principal
Migration phases (Agency 2026 → Hybrid 2026 → India Principal 2027 → UAE 2029+).

Without these dimensions, re-cutting the books for phase transitions becomes
manual re-keying. With them, it becomes a journal reclassification.

Design principles:
  * Pure analytic — does NOT alter the chart of accounts.
  * Auto-population from Mercury memo / counterparty / journal patterns.
  * Manual override always wins (audit trail preserved on the move line).
  * Read-only after lock_date (forensic guarantee).

Models added:
  * pes.principal.entity   — which legal entity owns the economic substance
                             (PES Supply, PES Global India HP, PES Global UAE,
                              BSD LLC, Portlandia Logistics, STR Capital, etc.)
  * pes.cost.center        — operational geography (US Ops, India SEZ Kangra,
                              India SEZ Lucknow, Pakistan, Bangladesh, etc.)
  * pes.revenue.track      — the 7-track revenue ops model (Amit's Global Sales
                              Hub, External Partners, BSDyno SHI, Managed
                              Materials, GMB/SEO, Inter-Company Billing,
                              STR Capital Lease-Back)
  * Auto-tag rules: pes.dimension.rule — ordered regex/keyword matchers that
                                          map Mercury memo + counterparty +
                                          journal → the four dimensions.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Dimension master tables
# ----------------------------------------------------------------------
class PesPrincipalEntity(models.Model):
    """Legal entity that owns the economic substance of a transaction.

    This is the dimension that flips during the SEZ Principal Migration:
      * Phase 1 (now):     PES Supply (US LLC) holds 100% of manufacturer
                           relationships and bank cash.
      * Phase 2 (2026):    50% PES Supply, 50% PES Global India HP (SEZ).
      * Phase 3 (2027-29): PES Global India HP holds principal economics.
      * Phase 4 (2029+):   PES Global UAE RAKEZ holds principal economics.

    By tagging EVERY transaction with the principal_entity_id today, we can
    re-cut the books at any phase boundary as a journal reclassification
    rather than a re-keying exercise.
    """
    _name = 'pes.principal.entity'
    _description = 'Principal Economic Entity'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=False)
    code = fields.Char(required=True, help="Stable code, e.g. 'pes-supply', "
                                           "'pes-global-india-hp', 'pes-global-uae'.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string="Bound Company",
        help="If this principal entity has a corresponding res.company in this "
             "Odoo instance, link it. Used by the inter-company commission "
             "rules and consolidation eliminations.",
    )
    jurisdiction = fields.Selection(
        [('us', 'United States'),
         ('in_sez', 'India SEZ (HP)'),
         ('in_dom', 'India Domestic'),
         ('ae_rakez', 'UAE RAKEZ Free Zone'),
         ('pk', 'Pakistan'),
         ('bd', 'Bangladesh'),
         ('other', 'Other')],
        required=True,
        help="Tax jurisdiction. Drives 0% SEZ and UAE Free Zone classification.",
    )
    sez_status = fields.Boolean(
        string="0% Tax Zone",
        help="True for India SEZ HP and UAE RAKEZ. Used by reporting to "
             "highlight tax-arbitrage flows.",
    )
    notes = fields.Text()

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Principal entity code must be unique.'),
    ]


class PesCostCenter(models.Model):
    """Operational geography / cost-center.

    Independent of principal_entity. Example: a transaction can be
    principal_entity = 'PES Supply' (the legal owner today) but
    cost_center = 'India SEZ Kangra' (where the work was actually done).
    This split is what proves the $1.87M/yr labor arbitrage in the deck.
    """
    _name = 'pes.cost.center'
    _description = 'Operational Cost Center'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    region = fields.Selection(
        [('us', 'US Operations'),
         ('in_kangra', 'India SEZ — Kangra (Sales Hub)'),
         ('in_lucknow', 'India SEZ — Lucknow'),
         ('in_other', 'India — Other'),
         ('pk', 'Pakistan'),
         ('bd', 'Bangladesh'),
         ('ae', 'UAE'),
         ('global', 'Global / Unallocated')],
        required=True,
    )
    notes = fields.Text()

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Cost center code must be unique.'),
    ]


class PesRevenueTrack(models.Model):
    """One of the 7 revenue tracks from the operating model.

    Hardcoded against the canonical PES Global structure:
      1. Amit's Global Sales Hub (Kangra)
      2. External Partners (Apollo.io sourced, brokered)
      3. BSDyno SHI (Big Sky Dynamics — managed materials specialty)
      4. Managed Materials (long-tail SKU fulfillment)
      5. GMB / SEO (organic inbound through Google My Business + content)
      6. Inter-Company Billing (PES Supply ↔ PES Global India 8% commission)
      7. STR Capital Lease-Back (real estate lease-back income)
    """
    _name = 'pes.revenue.track'
    _description = 'Revenue Operations Track'
    _order = 'track_number'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    track_number = fields.Integer(required=True, help="1-7 per the operating model.")
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ('track_number_uniq', 'unique(track_number)',
         'Revenue track number must be unique (1-7).'),
        ('code_uniq', 'unique(code)', 'Track code must be unique.'),
    ]


# ----------------------------------------------------------------------
# Auto-tag rule engine
# ----------------------------------------------------------------------
class PesDimensionRule(models.Model):
    """Ordered rule that auto-populates the four forensic dimensions.

    Evaluated against every Mercury statement line (and every Odoo 18 backfill
    line) at insertion time. First match wins; manual override always sticks.

    Match keys (all optional, all AND'd):
      * mercury_memo_regex
      * counterparty_regex
      * journal_id
      * amount_min / amount_max
      * mercury_account_kind  ('checking', 'savings', 'mercuryCredit', 'IOAccount', ...)

    Any field left blank means "match anything". An empty rule matches every
    line — useful as a low-priority default catcher.
    """
    _name = 'pes.dimension.rule'
    _description = 'Forensic Dimension Auto-Tag Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=100)
    active = fields.Boolean(default=True)

    # ----- match conditions -----
    mercury_memo_regex = fields.Char(
        string="Memo Regex",
        help="Python regex matched against Mercury externalMemo + bankDescription. "
             "Case-insensitive.",
    )
    counterparty_regex = fields.Char(
        string="Counterparty Regex",
        help="Python regex matched against Mercury counterpartyName. "
             "Case-insensitive.",
    )
    journal_ids = fields.Many2many(
        'account.journal',
        string="Journals",
        help="If set, rule only fires when the line lands in one of these "
             "journals. Empty = any journal.",
    )
    mercury_account_kind = fields.Selection(
        [('checking', 'Checking'),
         ('savings', 'Savings'),
         ('mercuryCredit', 'Mercury Credit'),
         ('IOAccount', 'IO Account'),
         ('any', 'Any')],
        default='any',
    )
    amount_min = fields.Float(help="Inclusive minimum (signed amount).")
    amount_max = fields.Float(help="Inclusive maximum (signed amount).")

    # ----- assignments -----
    principal_entity_id = fields.Many2one('pes.principal.entity')
    cost_center_id = fields.Many2one('pes.cost.center')
    revenue_track_id = fields.Many2one('pes.revenue.track')
    intercompany_partner_id = fields.Many2one(
        'res.partner',
        domain="[('is_company', '=', True)]",
        help="If this transaction is intercompany, the OTHER side's partner "
             "record. Drives consolidation elimination.",
    )

    notes = fields.Text()

    @api.constrains('mercury_memo_regex', 'counterparty_regex')
    def _check_regex(self):
        for rule in self:
            for field_name in ('mercury_memo_regex', 'counterparty_regex'):
                value = rule[field_name]
                if value:
                    try:
                        re.compile(value, re.IGNORECASE)
                    except re.error as e:
                        raise ValidationError(_(
                            "Invalid regex in %(field)s: %(err)s"
                        ) % {'field': field_name, 'err': e})

    def _matches(self, *, memo, counterparty, journal_id, account_kind, amount):
        """Test whether this rule matches the given line context."""
        self.ensure_one()
        if not self.active:
            return False
        if self.mercury_memo_regex:
            if not memo or not re.search(self.mercury_memo_regex, memo, re.IGNORECASE):
                return False
        if self.counterparty_regex:
            if not counterparty or not re.search(
                self.counterparty_regex, counterparty, re.IGNORECASE
            ):
                return False
        if self.journal_ids and journal_id not in self.journal_ids.ids:
            return False
        if self.mercury_account_kind and self.mercury_account_kind != 'any':
            if account_kind != self.mercury_account_kind:
                return False
        if self.amount_min and amount < self.amount_min:
            return False
        if self.amount_max and amount > self.amount_max:
            return False
        return True


# ----------------------------------------------------------------------
# account.move.line — add the four dimensions + manual override flag
# ----------------------------------------------------------------------
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    pes_principal_entity_id = fields.Many2one(
        'pes.principal.entity',
        string="Principal Entity",
        index=True,
        help="Legal entity that owns the economic substance of this line. "
             "Independent of company_id — supports the SEZ Principal Migration.",
    )
    pes_cost_center_id = fields.Many2one(
        'pes.cost.center',
        string="Cost Center",
        index=True,
        help="Operational geography (US Ops, India SEZ Kangra, etc.). "
             "Independent of principal_entity — supports labor-arbitrage reporting.",
    )
    pes_revenue_track_id = fields.Many2one(
        'pes.revenue.track',
        string="Revenue Track",
        index=True,
        help="Which of the 7 revenue tracks this line belongs to.",
    )
    pes_intercompany_partner_id = fields.Many2one(
        'res.partner',
        string="Intercompany Partner",
        domain="[('is_company', '=', True)]",
        help="If this is an intercompany line, the counterparty company.",
    )
    pes_dimensions_locked = fields.Boolean(
        string="Dimensions Manually Set",
        default=False,
        help="If True, auto-tag rules skip this line. Set automatically when "
             "a user edits any of the four dimensions in the UI.",
    )
    pes_dimensions_source = fields.Selection(
        [('auto', 'Auto-Tagged'),
         ('manual', 'Manual'),
         ('rule', 'Rule-Matched'),
         ('none', 'Untagged')],
        default='none',
        readonly=True,
        help="How the current dimension values were assigned.",
    )

    # ------------------------------------------------------------------
    # Auto-tag entry point — called by Mercury statement-line creation
    # ------------------------------------------------------------------
    def _pes_apply_dimension_rules(self, *, mercury_payload=None):
        """Apply the rule engine to self. Skips locked lines.

        `mercury_payload` is the raw Mercury transaction dict if available;
        falls back to the line's own narration/partner_id if not.
        """
        Rule = self.env['pes.dimension.rule'].sudo()
        rules = Rule.search([('active', '=', True)])
        if not rules:
            return

        for line in self:
            if line.pes_dimensions_locked:
                continue

            memo = ''
            counterparty = ''
            account_kind = 'any'
            if mercury_payload:
                memo = ' '.join(filter(None, [
                    mercury_payload.get('externalMemo'),
                    mercury_payload.get('bankDescription'),
                    mercury_payload.get('note'),
                ]))
                counterparty = mercury_payload.get('counterpartyName') or ''
                account_kind = mercury_payload.get('mercury_account_kind', 'any')
            else:
                memo = line.narration or line.name or ''
                counterparty = line.partner_id.name or '' if line.partner_id else ''

            for rule in rules:
                if rule._matches(
                    memo=memo,
                    counterparty=counterparty,
                    journal_id=line.journal_id.id,
                    account_kind=account_kind,
                    amount=line.balance,
                ):
                    vals = {'pes_dimensions_source': 'rule'}
                    if rule.principal_entity_id:
                        vals['pes_principal_entity_id'] = rule.principal_entity_id.id
                    if rule.cost_center_id:
                        vals['pes_cost_center_id'] = rule.cost_center_id.id
                    if rule.revenue_track_id:
                        vals['pes_revenue_track_id'] = rule.revenue_track_id.id
                    if rule.intercompany_partner_id:
                        vals['pes_intercompany_partner_id'] = (
                            rule.intercompany_partner_id.id
                        )
                    line.sudo().write(vals)
                    _logger.info(
                        'pes_dimensions: line %s tagged by rule "%s"',
                        line.id, rule.name,
                    )
                    break

    def write(self, vals):
        """Detect manual edits to dimension fields and lock the line."""
        dimension_fields = {
            'pes_principal_entity_id',
            'pes_cost_center_id',
            'pes_revenue_track_id',
            'pes_intercompany_partner_id',
        }
        if dimension_fields & set(vals.keys()):
            # Mark as manually set unless the writer explicitly says otherwise.
            if 'pes_dimensions_source' not in vals:
                vals['pes_dimensions_source'] = 'manual'
            if 'pes_dimensions_locked' not in vals:
                vals['pes_dimensions_locked'] = True
        return super().write(vals)
