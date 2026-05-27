from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PropertyShowing(models.Model):
    _name = 'villeside.showing'
    _description = 'Property Showing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'showing_date desc'

    name = fields.Char(string='Showing Reference', compute='_compute_name', store=True)
    state = fields.Selection([
        ('requested', 'Requested'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled'),
    ], string='Status', default='requested', tracking=True)
    showing_type = fields.Selection([
        ('in_person', 'In-Person'),
        ('virtual', 'Virtual Tour'),
        ('open_house', 'Open House'),
        ('private', 'Private Showing'),
        ('broker_open', 'Broker Open'),
    ], string='Showing Type', default='in_person', required=True)
    property_id = fields.Many2one('villeside.property.listing', string='Property', required=True)
    lead_id = fields.Many2one('crm.lead', string='Lead')
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    agent_id = fields.Many2one('res.users', string='Showing Agent', required=True)
    listing_agent_id = fields.Many2one('res.users', string='Listing Agent')
    showing_date = fields.Datetime(string='Showing Date/Time', required=True)
    duration_minutes = fields.Integer(string='Duration (min)', default=30)
    end_time = fields.Datetime(string='End Time', compute='_compute_end_time', store=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    notes = fields.Text(string='Notes')
    lockbox_code = fields.Char(string='Lockbox Code')
    access_instructions = fields.Text(string='Access Instructions')
    # Feedback
    feedback_rating = fields.Selection([
        ('1', 'Not Interested'),
        ('2', 'Somewhat Interested'),
        ('3', 'Interested'),
        ('4', 'Very Interested'),
        ('5', 'Ready to Make Offer'),
    ], string='Client Interest Level')
    feedback_notes = fields.Text(string='Feedback Notes')
    price_feedback = fields.Selection([
        ('too_high', 'Price Too High'),
        ('fair', 'Fair Price'),
        ('good_value', 'Good Value'),
    ], string='Price Feedback')
    condition_feedback = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('needs_work', 'Needs Work'),
    ], string='Condition Feedback')
    would_recommend = fields.Boolean(string='Would Recommend')
    follow_up_needed = fields.Boolean(string='Follow-Up Needed', default=True)
    follow_up_date = fields.Date(string='Follow-Up Date')
    # Confirmation
    client_confirmed = fields.Boolean(string='Client Confirmed', default=False)
    agent_confirmed = fields.Boolean(string='Agent Confirmed', default=False)
    reminder_sent = fields.Boolean(string='Reminder Sent', default=False)

    @api.depends('property_id', 'showing_date')
    def _compute_name(self):
        for rec in self:
            prop = rec.property_id.name or 'Property'
            date = rec.showing_date.strftime('%m/%d %H:%M') if rec.showing_date else ''
            rec.name = '%s - %s' % (prop, date)

    @api.depends('showing_date', 'duration_minutes')
    def _compute_end_time(self):
        for rec in self:
            if rec.showing_date and rec.duration_minutes:
                rec.end_time = rec.showing_date + timedelta(minutes=rec.duration_minutes)
            else:
                rec.end_time = rec.showing_date

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_no_show(self):
        self.write({'state': 'no_show'})

    @api.model
    def _cron_send_reminders(self):
        tomorrow = fields.Datetime.now() + timedelta(hours=24)
        upcoming = self.search([
            ('state', '=', 'confirmed'),
            ('showing_date', '<=', tomorrow),
            ('showing_date', '>=', fields.Datetime.now()),
            ('reminder_sent', '=', False),
        ])
        for showing in upcoming:
            template = self.env.ref('villeside_showing.email_template_showing_reminder', raise_if_not_found=False)
            if template:
                template.send_mail(showing.id, force_send=True)
            showing.write({'reminder_sent': True})


class OpenHouse(models.Model):
    _name = 'villeside.open.house'
    _description = 'Open House Event'
    _inherit = ['mail.thread']
    _order = 'start_date desc'

    name = fields.Char(string='Open House Name', required=True)
    property_id = fields.Many2one('villeside.property.listing', string='Property', required=True)
    host_agent_id = fields.Many2one('res.users', string='Host Agent', required=True)
    start_date = fields.Datetime(string='Start Date/Time', required=True)
    end_date = fields.Datetime(string='End Date/Time', required=True)
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', tracking=True)
    visitor_ids = fields.One2many('villeside.open.house.visitor', 'open_house_id', string='Visitors')
    visitor_count = fields.Integer(compute='_compute_visitor_count', string='Visitors')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    notes = fields.Text(string='Notes')
    refreshments = fields.Boolean(string='Refreshments', default=False)
    signage_placed = fields.Boolean(string='Signage Placed', default=False)
    marketing_flyers = fields.Boolean(string='Marketing Flyers Ready', default=False)

    @api.depends('visitor_ids')
    def _compute_visitor_count(self):
        for rec in self:
            rec.visitor_count = len(rec.visitor_ids)


class OpenHouseVisitor(models.Model):
    _name = 'villeside.open.house.visitor'
    _description = 'Open House Visitor'

    open_house_id = fields.Many2one('villeside.open.house', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Visitor')
    name = fields.Char(string='Name')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    interest_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Interest Level')
    has_agent = fields.Boolean(string='Has Agent', default=False)
    agent_name = fields.Char(string='Agent Name')
    pre_approved = fields.Boolean(string='Pre-Approved', default=False)
    notes = fields.Text(string='Notes')
    lead_created = fields.Boolean(string='Lead Created', default=False)
    lead_id = fields.Many2one('crm.lead', string='Created Lead')