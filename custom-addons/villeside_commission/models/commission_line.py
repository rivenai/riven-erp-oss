from odoo import models, fields, api
from datetime import date


class CommissionLine(models.Model):
    _name = 'villeside.commission.line'
    _description = 'Commission Transaction Line'
    _order = 'close_date desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    plan_id = fields.Many2one('villeside.commission.plan', string='Commission Plan')
    agent_id = fields.Many2one('hr.employee', string='Agent', required=True)
    lead_id = fields.Many2one('crm.lead', string='CRM Opportunity')
    property_address = fields.Char(string='Property Address')
    close_date = fields.Date(string='Close Date')
    sale_price = fields.Monetary(string='Sale Price', currency_field='currency_id')
    commission_rate = fields.Float(string='Commission Rate %', default=3.0)
    gross_commission = fields.Monetary(string='Gross Commission (GCI)', compute='_compute_amounts', store=True, currency_field='currency_id')
    agent_split_pct = fields.Float(string='Agent Split %')
    agent_amount = fields.Monetary(string='Agent Share', compute='_compute_amounts', store=True, currency_field='currency_id')
    broker_amount = fields.Monetary(string='Broker Share', compute='_compute_amounts', store=True, currency_field='currency_id')
    transaction_fee = fields.Monetary(string='Transaction Fee', currency_field='currency_id')
    admin_fee = fields.Monetary(string='Admin Fee', currency_field='currency_id')
    net_agent_payout = fields.Monetary(string='Net Agent Payout', compute='_compute_amounts', store=True, currency_field='currency_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Disbursement'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status')
    payment_date = fields.Date(string='Payment Date')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    side = fields.Selection([('buy', 'Buy Side'), ('sell', 'Sell Side'), ('dual', 'Dual Agency')], string='Side')
    team_lead_override_pct = fields.Float(string='Team Lead Override %')
    team_lead_override_amount = fields.Monetary(string='Team Lead Override', compute='_compute_amounts', store=True, currency_field='currency_id')
    notes = fields.Text(string='Notes')

    @api.depends('agent_id', 'property_address', 'close_date')
    def _compute_name(self):
        for rec in self:
            parts = [rec.agent_id.name or '', rec.property_address or '', str(rec.close_date or '')]
            rec.name = ' - '.join(filter(None, parts))

    @api.depends('sale_price', 'commission_rate', 'agent_split_pct', 'transaction_fee', 'admin_fee', 'team_lead_override_pct')
    def _compute_amounts(self):
        for rec in self:
            rec.gross_commission = rec.sale_price * (rec.commission_rate / 100.0)
            rec.agent_amount = rec.gross_commission * (rec.agent_split_pct / 100.0)
            rec.broker_amount = rec.gross_commission - rec.agent_amount
            rec.team_lead_override_amount = rec.gross_commission * (rec.team_lead_override_pct / 100.0)
            rec.net_agent_payout = rec.agent_amount - (rec.transaction_fee or 0) - (rec.admin_fee or 0) - rec.team_lead_override_amount

    def action_mark_paid(self):
        self.write({'state': 'paid', 'payment_date': date.today()})