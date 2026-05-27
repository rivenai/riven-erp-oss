from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LeadRoutingRule(models.Model):
    _name = 'villeside.lead.routing.rule'
    _description = 'Lead Routing Rule'
    _order = 'sequence'

    name = fields.Char(string='Rule Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    routing_type = fields.Selection([
        ('round_robin', 'Round Robin'),
        ('territory', 'Territory Based'),
        ('price_range', 'Price Range'),
        ('source', 'Lead Source'),
        ('shark_tank', 'Shark Tank (First Claim)'),
    ], string='Routing Type', required=True, default='round_robin')

    # Filters
    min_price = fields.Float(string='Min Price')
    max_price = fields.Float(string='Max Price')
    zip_codes = fields.Char(string='ZIP Codes (comma-separated)')
    lead_source = fields.Char(string='Lead Source')
    team_id = fields.Many2one('crm.team', string='Sales Team')

    # Agents pool
    agent_ids = fields.Many2many('hr.employee', string='Agent Pool')
    last_assigned_agent_id = fields.Many2one('hr.employee', string='Last Assigned Agent')

    # Shark tank settings
    shark_tank_timeout_hours = fields.Integer(string='Shark Tank Timeout (Hours)', default=4)

    # Speed-to-lead
    max_response_minutes = fields.Integer(string='Max Response Time (Minutes)', default=5)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def get_next_agent(self):
        self.ensure_one()
        if not self.agent_ids:
            return False
        agents = self.agent_ids.sorted('id')
        if self.routing_type == 'round_robin':
            if not self.last_assigned_agent_id or self.last_assigned_agent_id not in agents:
                next_agent = agents[0]
            else:
                idx = list(agents.ids).index(self.last_assigned_agent_id.id)
                next_agent = agents[(idx + 1) % len(agents)]
            self.last_assigned_agent_id = next_agent
            return next_agent
        return agents[0]


class LeadSpeedTracker(models.Model):
    _name = 'villeside.lead.speed'
    _description = 'Lead Speed-to-Lead Tracker'
    _order = 'lead_received_time desc'

    lead_id = fields.Many2one('crm.lead', string='Lead', required=True)
    agent_id = fields.Many2one('hr.employee', string='Assigned Agent')
    lead_received_time = fields.Datetime(string='Lead Received')
    first_contact_time = fields.Datetime(string='First Contact')
    response_seconds = fields.Integer(string='Response Time (Seconds)', compute='_compute_response')
    met_sla = fields.Boolean(string='Met SLA', compute='_compute_response')
    routing_rule_id = fields.Many2one('villeside.lead.routing.rule', string='Routing Rule')

    @api.depends('lead_received_time', 'first_contact_time')
    def _compute_response(self):
        for rec in self:
            if rec.lead_received_time and rec.first_contact_time:
                delta = rec.first_contact_time - rec.lead_received_time
                rec.response_seconds = int(delta.total_seconds())
                sla = (rec.routing_rule_id.max_response_minutes or 5) * 60
                rec.met_sla = rec.response_seconds <= sla
            else:
                rec.response_seconds = 0
                rec.met_sla = False


class CrmLeadInherit(models.Model):
    _inherit = 'crm.lead'

    lead_score = fields.Integer(string='Lead Score', default=0)
    lead_source_detail = fields.Char(string='Lead Source Detail')
    property_interest_type = fields.Selection([
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
        ('investor', 'Investor'),
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
    ], string='Interest Type')
    budget_min = fields.Monetary(string='Budget Min', currency_field='company_currency')
    budget_max = fields.Monetary(string='Budget Max', currency_field='company_currency')
    preferred_zip_codes = fields.Char(string='Preferred ZIP Codes')
    preferred_neighborhoods = fields.Char(string='Preferred Neighborhoods')
    bedrooms_min = fields.Integer(string='Min Bedrooms')
    pre_approved = fields.Boolean(string='Pre-Approved')
    pre_approval_amount = fields.Monetary(string='Pre-Approval Amount', currency_field='company_currency')
    lender_name = fields.Char(string='Lender Name')
    speed_tracker_ids = fields.One2many('villeside.lead.speed', 'lead_id', string='Speed Tracking')