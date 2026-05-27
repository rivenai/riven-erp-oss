from odoo import models, fields, api, http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class IDXConfig(models.Model):
    _name = 'villeside.idx.config'
    _description = 'IDX/MLS Integration Configuration'

    name = fields.Char(string='Feed Name', required=True)
    active = fields.Boolean(default=True)
    feed_type = fields.Selection([
        ('rets', 'RETS'),
        ('reso_web_api', 'RESO Web API'),
        ('idx_broker', 'IDX Broker'),
        ('listhub', 'ListHub'),
        ('spark', 'Spark API'),
        ('bridge', 'Bridge Interactive'),
        ('custom', 'Custom API'),
    ], string='Feed Type', required=True)
    api_url = fields.Char(string='API URL')
    api_key = fields.Char(string='API Key')
    api_secret = fields.Char(string='API Secret')
    username = fields.Char(string='Username')
    mls_id = fields.Char(string='MLS ID')
    last_sync = fields.Datetime(string='Last Sync')
    sync_interval_hours = fields.Integer(string='Sync Interval (Hours)', default=6)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    auto_publish = fields.Boolean(string='Auto-Publish to Website', default=True)
    import_photos = fields.Boolean(string='Import Photos', default=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('error', 'Error'),
        ('disabled', 'Disabled'),
    ], string='Status', default='disabled')
    error_message = fields.Text(string='Last Error')
    total_imported = fields.Integer(string='Total Imported')


class WebsitePropertySearch(models.Model):
    _name = 'villeside.website.search'
    _description = 'Website Property Search'
    _order = 'create_date desc'

    visitor_id = fields.Many2one('res.partner', string='Visitor')
    session_id = fields.Char(string='Session ID')
    search_type = fields.Selection([
        ('buy', 'Buy'),
        ('rent', 'Rent'),
        ('commercial', 'Commercial'),
    ], string='Search Type')
    location = fields.Char(string='Location Search')
    min_price = fields.Float(string='Min Price')
    max_price = fields.Float(string='Max Price')
    bedrooms_min = fields.Integer(string='Min Bedrooms')
    bathrooms_min = fields.Integer(string='Min Bathrooms')
    sqft_min = fields.Integer(string='Min Sq Ft')
    sqft_max = fields.Integer(string='Max Sq Ft')
    property_type = fields.Char(string='Property Type Filter')
    lot_size_min = fields.Float(string='Min Lot Size')
    year_built_min = fields.Integer(string='Min Year Built')
    keywords = fields.Char(string='Keywords')
    results_count = fields.Integer(string='Results Found')
    saved = fields.Boolean(string='Search Saved', default=False)
    alert_enabled = fields.Boolean(string='Email Alerts', default=False)
    alert_frequency = fields.Selection([
        ('instant', 'Instant'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ], string='Alert Frequency')


class WebsiteLeadCapture(models.Model):
    _name = 'villeside.website.lead'
    _description = 'Website Lead Capture'
    _order = 'create_date desc'

    name = fields.Char(string='Name')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    source = fields.Selection([
        ('property_inquiry', 'Property Inquiry'),
        ('contact_form', 'Contact Form'),
        ('home_valuation', 'Home Valuation'),
        ('mortgage_calc', 'Mortgage Calculator'),
        ('saved_search', 'Saved Search'),
        ('schedule_showing', 'Schedule Showing'),
        ('newsletter', 'Newsletter Signup'),
        ('chat', 'Live Chat'),
        ('social', 'Social Media'),
    ], string='Lead Source')
    property_id = fields.Many2one('villeside.property.listing', string='Property of Interest')
    message = fields.Text(string='Message')
    lead_id = fields.Many2one('crm.lead', string='Created CRM Lead')
    converted = fields.Boolean(string='Converted to Lead', default=False)
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char(string='User Agent')
    referrer = fields.Char(string='Referrer URL')
    utm_source = fields.Char(string='UTM Source')
    utm_medium = fields.Char(string='UTM Medium')
    utm_campaign = fields.Char(string='UTM Campaign')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def action_convert_to_lead(self):
        self.ensure_one()
        partner = self.env['res.partner'].search([('email', '=', self.email)], limit=1)
        if not partner and self.email:
            partner = self.env['res.partner'].create({
                'name': self.name or self.email,
                'email': self.email,
                'phone': self.phone,
            })
        lead = self.env['crm.lead'].create({
            'name': 'Web: %s - %s' % (self.get_selection_label('source', self.source), self.name or self.email),
            'partner_id': partner.id if partner else False,
            'email_from': self.email,
            'phone': self.phone,
            'description': self.message,
            'type': 'lead',
            'source_id': self.env.ref('utm.utm_source_website', raise_if_not_found=False).id if self.env.ref('utm.utm_source_website', raise_if_not_found=False) else False,
        })
        self.write({'lead_id': lead.id, 'converted': True})
        return lead

    def get_selection_label(self, field_name, value):
        return dict(self._fields[field_name].selection).get(value, value)