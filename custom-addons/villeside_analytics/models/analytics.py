from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class AgentPerformance(models.Model):
    _name = 'villeside.analytics.agent'
    _description = 'Agent Performance Analytics'
    _order = 'date desc'
    _rec_name = 'agent_id'

    agent_id = fields.Many2one('res.users', string='Agent', required=True)
    date = fields.Date(string='Period Date', required=True)
    period_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Period', default='monthly')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    # Lead Metrics
    leads_assigned = fields.Integer(string='Leads Assigned')
    leads_contacted = fields.Integer(string='Leads Contacted')
    leads_converted = fields.Integer(string='Leads Converted')
    conversion_rate = fields.Float(string='Conversion Rate %', compute='_compute_rates')
    avg_response_time_min = fields.Float(string='Avg Response Time (min)')
    # Transaction Metrics
    listings_taken = fields.Integer(string='Listings Taken')
    listings_sold = fields.Integer(string='Listings Sold')
    buyer_closings = fields.Integer(string='Buyer Closings')
    total_volume = fields.Monetary(string='Total Volume', currency_field='currency_id')
    avg_sale_price = fields.Monetary(string='Avg Sale Price', currency_field='currency_id')
    avg_days_on_market = fields.Float(string='Avg Days on Market')
    list_to_sale_ratio = fields.Float(string='List-to-Sale Ratio %')
    # Revenue Metrics
    gross_commission = fields.Monetary(string='Gross Commission', currency_field='currency_id')
    net_commission = fields.Monetary(string='Net Commission', currency_field='currency_id')
    pending_commission = fields.Monetary(string='Pending Commission', currency_field='currency_id')
    # Activity Metrics
    showings_conducted = fields.Integer(string='Showings Conducted')
    open_houses = fields.Integer(string='Open Houses Held')
    calls_made = fields.Integer(string='Calls Made')
    emails_sent = fields.Integer(string='Emails Sent')
    appointments_set = fields.Integer(string='Appointments Set')

    @api.depends('leads_assigned', 'leads_converted')
    def _compute_rates(self):
        for rec in self:
            if rec.leads_assigned:
                rec.conversion_rate = (rec.leads_converted / rec.leads_assigned) * 100
            else:
                rec.conversion_rate = 0.0

    @api.model
    def _cron_compute_monthly_stats(self):
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        agents = self.env['res.users'].search([('share', '=', False)])
        for agent in agents:
            leads = self.env['crm.lead'].search([
                ('user_id', '=', agent.id),
                ('create_date', '>=', first_of_month),
            ])
            won = leads.filtered(lambda l: l.stage_id.is_won)
            self.create({
                'agent_id': agent.id,
                'date': first_of_month,
                'period_type': 'monthly',
                'leads_assigned': len(leads),
                'leads_converted': len(won),
            })


class MarketAnalytics(models.Model):
    _name = 'villeside.analytics.market'
    _description = 'Market Analytics Snapshot'
    _order = 'date desc'

    name = fields.Char(string='Snapshot Name', required=True)
    date = fields.Date(string='Date', required=True)
    zip_code = fields.Char(string='ZIP Code')
    neighborhood = fields.Char(string='Neighborhood')
    city = fields.Char(string='City')
    state_code = fields.Char(string='State')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    median_list_price = fields.Monetary(string='Median List Price', currency_field='currency_id')
    median_sale_price = fields.Monetary(string='Median Sale Price', currency_field='currency_id')
    avg_price_per_sqft = fields.Monetary(string='Avg Price/SqFt', currency_field='currency_id')
    active_listings = fields.Integer(string='Active Listings')
    new_listings = fields.Integer(string='New Listings')
    pending_sales = fields.Integer(string='Pending Sales')
    closed_sales = fields.Integer(string='Closed Sales')
    avg_days_on_market = fields.Float(string='Avg Days on Market')
    months_of_inventory = fields.Float(string='Months of Inventory')
    list_to_sale_ratio = fields.Float(string='List-to-Sale Ratio %')
    price_change_pct = fields.Float(string='Price Change YoY %')
    absorption_rate = fields.Float(string='Absorption Rate')
    notes = fields.Text(string='Notes')


class PipelineSnapshot(models.Model):
    _name = 'villeside.analytics.pipeline'
    _description = 'Pipeline Analytics Snapshot'
    _order = 'date desc'

    date = fields.Date(string='Date', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    total_leads = fields.Integer(string='Total Active Leads')
    new_leads = fields.Integer(string='New Leads (Period)')
    qualified_leads = fields.Integer(string='Qualified Leads')
    proposals_sent = fields.Integer(string='Proposals/Offers Sent')
    pending_closings = fields.Integer(string='Pending Closings')
    closed_won = fields.Integer(string='Closed Won')
    closed_lost = fields.Integer(string='Closed Lost')
    pipeline_value = fields.Monetary(string='Pipeline Value', currency_field='currency_id')
    weighted_value = fields.Monetary(string='Weighted Pipeline Value', currency_field='currency_id')
    avg_deal_size = fields.Monetary(string='Avg Deal Size', currency_field='currency_id')
    win_rate = fields.Float(string='Win Rate %')
    avg_sales_cycle_days = fields.Float(string='Avg Sales Cycle (Days)')