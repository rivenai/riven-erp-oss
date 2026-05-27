from odoo import models, fields, api


class PropertyListing(models.Model):
    _name = 'villeside.property'
    _description = 'Property Listing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'list_date desc'

    name = fields.Char(string='Listing Title', compute='_compute_name', store=True)
    mls_number = fields.Char(string='MLS #', index=True)
    flexmls_id = fields.Char(string='FlexMLS ID')
    street = fields.Char(string='Street Address', required=True)
    street2 = fields.Char(string='Unit/Suite')
    city = fields.Char(string='City', default='Louisville')
    state_id = fields.Many2one('res.country.state', string='State')
    zip_code = fields.Char(string='ZIP Code')
    county = fields.Char(string='County', default='Jefferson')
    neighborhood = fields.Char(string='Neighborhood')
    subdivision = fields.Char(string='Subdivision')

    # Property details
    property_type = fields.Selection([
        ('single_family', 'Single Family'),
        ('condo', 'Condo/Townhouse'),
        ('multi_family', 'Multi-Family'),
        ('land', 'Land/Lot'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('mixed_use', 'Mixed Use'),
        ('farm', 'Farm/Ranch'),
    ], string='Property Type', required=True, tracking=True)
    bedrooms = fields.Integer(string='Bedrooms')
    bathrooms_full = fields.Integer(string='Full Baths')
    bathrooms_half = fields.Integer(string='Half Baths')
    sqft_living = fields.Integer(string='Living Sq Ft')
    sqft_total = fields.Integer(string='Total Sq Ft')
    lot_size_acres = fields.Float(string='Lot Size (Acres)')
    lot_size_sqft = fields.Integer(string='Lot Size (Sq Ft)')
    year_built = fields.Integer(string='Year Built')
    stories = fields.Float(string='Stories')
    garage_spaces = fields.Integer(string='Garage Spaces')
    parking_type = fields.Char(string='Parking Type')
    basement = fields.Selection([('none', 'None'), ('partial', 'Partial'), ('full', 'Full'), ('finished', 'Finished')], string='Basement')
    pool = fields.Boolean(string='Pool')
    hoa_fee = fields.Monetary(string='HOA Fee (Monthly)', currency_field='currency_id')

    # Pricing
    list_price = fields.Monetary(string='List Price', tracking=True, currency_field='currency_id')
    original_list_price = fields.Monetary(string='Original List Price', currency_field='currency_id')
    sold_price = fields.Monetary(string='Sold Price', currency_field='currency_id')
    price_per_sqft = fields.Monetary(string='Price/Sq Ft', compute='_compute_price_sqft', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Dates
    list_date = fields.Date(string='List Date', tracking=True)
    pending_date = fields.Date(string='Pending Date')
    sold_date = fields.Date(string='Sold Date')
    expiration_date = fields.Date(string='Listing Expiration')
    dom = fields.Integer(string='Days on Market', compute='_compute_dom')

    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('coming_soon', 'Coming Soon'),
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('under_contract', 'Under Contract'),
        ('sold', 'Sold'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)

    # Agents and contacts
    listing_agent_id = fields.Many2one('hr.employee', string='Listing Agent')
    co_listing_agent_id = fields.Many2one('hr.employee', string='Co-Listing Agent')
    seller_id = fields.Many2one('res.partner', string='Seller/Owner')
    buyer_id = fields.Many2one('res.partner', string='Buyer')
    buyer_agent_id = fields.Many2one('res.partner', string='Buyer Agent')
    lead_id = fields.Many2one('crm.lead', string='CRM Opportunity')

    # Commission
    listing_commission_pct = fields.Float(string='Listing Side Commission %', default=3.0)
    buyer_commission_pct = fields.Float(string='Buyer Side Commission %', default=3.0)
    total_commission = fields.Monetary(string='Total Commission', compute='_compute_commission', currency_field='currency_id')

    # Media
    image_ids = fields.Many2many('ir.attachment', string='Photos')
    virtual_tour_url = fields.Char(string='Virtual Tour URL')
    video_url = fields.Char(string='Video URL')

    # Description
    description = fields.Html(string='Public Description')
    private_remarks = fields.Text(string='Agent Remarks (Private)')
    showing_instructions = fields.Text(string='Showing Instructions')

    # Features
    feature_ids = fields.Many2many('villeside.property.feature', string='Features')
    school_district = fields.Char(string='School District')
    zoning = fields.Char(string='Zoning')
    tax_amount = fields.Monetary(string='Annual Tax', currency_field='currency_id')
    tax_year = fields.Integer(string='Tax Year')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('street', 'city', 'zip_code')
    def _compute_name(self):
        for rec in self:
            parts = [rec.street or '', rec.city or '', rec.zip_code or '']
            rec.name = ', '.join(filter(None, parts))

    @api.depends('list_price', 'sqft_living')
    def _compute_price_sqft(self):
        for rec in self:
            rec.price_per_sqft = rec.list_price / rec.sqft_living if rec.sqft_living else 0

    @api.depends('list_date')
    def _compute_dom(self):
        for rec in self:
            if rec.list_date:
                end = rec.sold_date or rec.pending_date or fields.Date.today()
                rec.dom = (end - rec.list_date).days
            else:
                rec.dom = 0

    @api.depends('sold_price', 'list_price', 'listing_commission_pct', 'buyer_commission_pct')
    def _compute_commission(self):
        for rec in self:
            price = rec.sold_price or rec.list_price or 0
            rec.total_commission = price * ((rec.listing_commission_pct + rec.buyer_commission_pct) / 100.0)


class PropertyFeature(models.Model):
    _name = 'villeside.property.feature'
    _description = 'Property Feature Tag'
    _order = 'name'

    name = fields.Char(required=True)
    category = fields.Selection([
        ('interior', 'Interior'),
        ('exterior', 'Exterior'),
        ('community', 'Community'),
        ('green', 'Green/Energy'),
    ], string='Category')