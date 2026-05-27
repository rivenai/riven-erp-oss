from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CommissionPlan(models.Model):
    _name = 'villeside.commission.plan'
    _description = 'Commission Plan'
    _order = 'name'

    name = fields.Char(string='Plan Name', required=True)
    plan_type = fields.Selection([
        ('fixed', 'Fixed Split'),
        ('tiered', 'Tiered by Volume'),
        ('capped', 'Capped Split'),
        ('flat_fee', '100% Flat Fee'),
    ], string='Plan Type', required=True, default='fixed')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # Fixed split fields
    agent_split_pct = fields.Float(string='Agent Split %', default=70.0)
    broker_split_pct = fields.Float(string='Broker Split %', compute='_compute_broker_split')

    # Cap fields
    annual_cap = fields.Monetary(string='Annual Cap Amount', currency_field='currency_id')
    post_cap_agent_pct = fields.Float(string='Post-Cap Agent %', default=100.0)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Flat fee fields
    flat_fee_per_txn = fields.Monetary(string='Flat Fee per Transaction', currency_field='currency_id')

    # Tiered volume fields
    tier_line_ids = fields.One2many('villeside.commission.tier', 'plan_id', string='Volume Tiers')

    # Additional fees
    transaction_fee = fields.Monetary(string='Transaction Fee', currency_field='currency_id')
    eo_insurance_fee = fields.Monetary(string='E&O Insurance Fee (Monthly)', currency_field='currency_id')
    desk_fee = fields.Monetary(string='Desk Fee (Monthly)', currency_field='currency_id')
    admin_fee = fields.Monetary(string='Admin Fee per Txn', currency_field='currency_id')

    line_ids = fields.One2many('villeside.commission.line', 'plan_id', string='Commission Lines')

    @api.depends('agent_split_pct')
    def _compute_broker_split(self):
        for rec in self:
            rec.broker_split_pct = 100.0 - rec.agent_split_pct


class CommissionTier(models.Model):
    _name = 'villeside.commission.tier'
    _description = 'Commission Volume Tier'
    _order = 'min_volume'

    plan_id = fields.Many2one('villeside.commission.plan', ondelete='cascade')
    min_volume = fields.Monetary(string='Min Volume', currency_field='currency_id')
    max_volume = fields.Monetary(string='Max Volume', currency_field='currency_id')
    agent_split_pct = fields.Float(string='Agent Split %')
    currency_id = fields.Many2one(related='plan_id.currency_id')


class AgentCommissionProfile(models.Model):
    _name = 'villeside.agent.commission'
    _description = 'Agent Commission Profile'

    employee_id = fields.Many2one('hr.employee', string='Agent', required=True)
    plan_id = fields.Many2one('villeside.commission.plan', string='Commission Plan', required=True)
    anniversary_date = fields.Date(string='Anniversary Date')
    ytd_gci = fields.Monetary(string='YTD Gross Commission Income', currency_field='currency_id')
    ytd_broker_paid = fields.Monetary(string='YTD Broker Share Paid', currency_field='currency_id')
    cap_reached = fields.Boolean(string='Cap Reached', compute='_compute_cap_status')
    cap_reached_date = fields.Date(string='Cap Reached Date')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.depends('ytd_broker_paid', 'plan_id.annual_cap')
    def _compute_cap_status(self):
        for rec in self:
            if rec.plan_id.plan_type == 'capped' and rec.plan_id.annual_cap:
                rec.cap_reached = rec.ytd_broker_paid >= rec.plan_id.annual_cap
            else:
                rec.cap_reached = False