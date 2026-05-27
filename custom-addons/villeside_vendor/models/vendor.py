from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class RealEstateVendor(models.Model):
    _name = 'villeside.vendor'
    _description = 'Real Estate Vendor/Service Provider'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Vendor Name', required=True)
    partner_id = fields.Many2one('res.partner', string='Contact')
    active = fields.Boolean(default=True)
    vendor_type = fields.Selection([
        ('inspector', 'Home Inspector'),
        ('appraiser', 'Appraiser'),
        ('title', 'Title Company'),
        ('escrow', 'Escrow Company'),
        ('lender', 'Lender/Mortgage'),
        ('insurance', 'Insurance'),
        ('photographer', 'Photographer'),
        ('stager', 'Home Stager'),
        ('contractor', 'General Contractor'),
        ('plumber', 'Plumber'),
        ('electrician', 'Electrician'),
        ('hvac', 'HVAC'),
        ('roofer', 'Roofer'),
        ('landscaper', 'Landscaper'),
        ('painter', 'Painter'),
        ('cleaner', 'Cleaning Service'),
        ('mover', 'Moving Company'),
        ('attorney', 'Real Estate Attorney'),
        ('surveyor', 'Surveyor'),
        ('pest', 'Pest Control'),
        ('handyman', 'Handyman'),
        ('locksmith', 'Locksmith'),
        ('other', 'Other'),
    ], string='Vendor Type', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')
    street = fields.Char(string='Street')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip_code = fields.Char(string='ZIP Code')
    license_number = fields.Char(string='License Number')
    insurance_policy = fields.Char(string='Insurance Policy #')
    insurance_expiry = fields.Date(string='Insurance Expiry')
    rating = fields.Float(string='Rating', default=0.0)
    review_count = fields.Integer(string='Reviews', compute='_compute_review_count')
    review_ids = fields.One2many('villeside.vendor.review', 'vendor_id', string='Reviews')
    service_area = fields.Char(string='Service Area')
    avg_response_time = fields.Char(string='Avg Response Time')
    preferred = fields.Boolean(string='Preferred Vendor', default=False)
    notes = fields.Text(string='Internal Notes')
    specialties = fields.Text(string='Specialties')
    hourly_rate = fields.Float(string='Hourly Rate')
    flat_rate = fields.Float(string='Flat Rate')
    payment_terms = fields.Char(string='Payment Terms')
    w9_on_file = fields.Boolean(string='W-9 on File', default=False)
    coi_on_file = fields.Boolean(string='COI on File', default=False)

    @api.depends('review_ids')
    def _compute_review_count(self):
        for rec in self:
            rec.review_count = len(rec.review_ids)
            if rec.review_ids:
                rec.rating = sum(r.rating for r in rec.review_ids) / len(rec.review_ids)


class VendorReview(models.Model):
    _name = 'villeside.vendor.review'
    _description = 'Vendor Review'
    _order = 'create_date desc'

    vendor_id = fields.Many2one('villeside.vendor', required=True, ondelete='cascade')
    reviewer_id = fields.Many2one('res.users', string='Reviewed By', default=lambda self: self.env.user)
    rating = fields.Float(string='Rating (1-5)', required=True)
    property_id = fields.Many2one('villeside.property.listing', string='Property')
    transaction_id = fields.Many2one('villeside.transaction', string='Transaction')
    review_text = fields.Text(string='Review')
    timeliness = fields.Selection([
        ('1', 'Poor'),
        ('2', 'Below Average'),
        ('3', 'Average'),
        ('4', 'Good'),
        ('5', 'Excellent'),
    ], string='Timeliness')
    quality = fields.Selection([
        ('1', 'Poor'),
        ('2', 'Below Average'),
        ('3', 'Average'),
        ('4', 'Good'),
        ('5', 'Excellent'),
    ], string='Quality of Work')
    communication = fields.Selection([
        ('1', 'Poor'),
        ('2', 'Below Average'),
        ('3', 'Average'),
        ('4', 'Good'),
        ('5', 'Excellent'),
    ], string='Communication')
    would_recommend = fields.Boolean(string='Would Recommend', default=True)