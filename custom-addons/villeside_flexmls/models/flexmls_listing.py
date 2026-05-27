import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SPARK_API_BASE = 'https://sparkapi.com/v1'


class FlexmlsListing(models.Model):
    _name = 'flexmls.listing'
    _description = 'FlexMLS Property Listing'
    _order = 'list_price desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Core Fields
    name = fields.Char('Listing Title', compute='_compute_name', store=True)
    mls_id = fields.Char('MLS ID', required=True, index=True, tracking=True)
    spark_id = fields.Char('Spark Listing ID', index=True)
    mls_status = fields.Selection([
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('sold', 'Sold'),
        ('expired', 'Expired'),
        ('withdrawn', 'Withdrawn'),
    ], string='MLS Status', default='active', tracking=True)

    # Address
    street_address = fields.Char('Street Address')
    city = fields.Char('City', default='Louisville')
    state = fields.Char('State', default='KY')
    zip_code = fields.Char('ZIP Code')
    county = fields.Char('County')
    subdivision = fields.Char('Subdivision')
    latitude = fields.Float('Latitude', digits=(10, 7))
    longitude = fields.Float('Longitude', digits=(10, 7))

    # Pricing
    list_price = fields.Float('List Price', tracking=True)
    original_price = fields.Float('Original Price')
    sold_price = fields.Float('Sold Price')
    price_per_sqft = fields.Float('Price/SqFt', compute='_compute_price_sqft', store=True)

    # Property Details
    property_type = fields.Selection([
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('land', 'Land'),
        ('multi_family', 'Multi-Family'),
        ('condo', 'Condo/Townhouse'),
    ], string='Property Type')
    bedrooms = fields.Integer('Bedrooms')
    bathrooms_full = fields.Integer('Full Baths')
    bathrooms_half = fields.Integer('Half Baths')
    sqft = fields.Integer('Square Feet')
    lot_size = fields.Float('Lot Size (Acres)')
    year_built = fields.Integer('Year Built')
    stories = fields.Integer('Stories')
    garage_spaces = fields.Integer('Garage Spaces')
    description = fields.Text('Public Remarks')

    # Dates
    list_date = fields.Date('List Date')
    sold_date = fields.Date('Sold Date')
    last_synced = fields.Datetime('Last Synced')

    # Media
    photo_urls = fields.Text('Photo URLs (JSON)')
    primary_photo_url = fields.Char('Primary Photo URL')
    virtual_tour_url = fields.Char('Virtual Tour URL')

    # Agent Info
    listing_agent_name = fields.Char('Listing Agent')
    listing_agent_phone = fields.Char('Agent Phone')
    listing_office = fields.Char('Listing Office')

    # Website
    website_published = fields.Boolean('Published on Website', default=True)
    website_url = fields.Char('Website URL', compute='_compute_website_url')

    @api.depends('street_address', 'city', 'mls_id')
    def _compute_name(self):
        for rec in self:
            parts = [rec.street_address or '', rec.city or '']
            rec.name = ', '.join(p for p in parts if p) or rec.mls_id or 'New Listing'

    @api.depends('list_price', 'sqft')
    def _compute_price_sqft(self):
        for rec in self:
            rec.price_per_sqft = rec.list_price / rec.sqft if rec.sqft else 0

    def _compute_website_url(self):
        for rec in self:
            rec.website_url = f'/listings/{rec.id}' if rec.id else ''

    def action_sync_from_spark(self):
        """Sync listings from Spark API"""
        config = self.env['flexmls.config'].get_config()
        if not config.api_key:
            raise UserError(_('Spark API key not configured.'))

        headers = {
            'Authorization': f'Bearer {config.access_token}',
            'X-SparkApi-User-Agent': 'VillesideRealty/1.0',
        }
        params = {
            '_filter': "MlsStatus Eq 'Active'",
            '_limit': 200,
            '_expand': 'Photos',
        }
        try:
            resp = requests.get(
                f'{SPARK_API_BASE}/listings',
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            listings = data.get('D', {}).get('Results', [])
            _logger.info('Fetched %d listings from Spark API', len(listings))
            for item in listings:
                self._upsert_listing(item)
        except requests.RequestException as e:
            _logger.error('Spark API error: %s', e)
            raise UserError(_('Failed to sync: %s') % str(e))

    def _upsert_listing(self, data):
        """Create or update a listing from Spark API data"""
        standard = data.get('StandardFields', {})
        mls_id = standard.get('ListingId', '')
        existing = self.search([('mls_id', '=', mls_id)], limit=1)
        photos = data.get('Photos', [])
        primary_photo = photos[0].get('Uri800', '') if photos else ''
        import json
        photo_json = json.dumps([p.get('Uri800', '') for p in photos])

        vals = {
            'mls_id': mls_id,
            'spark_id': data.get('Id', ''),
            'street_address': standard.get('UnparsedAddress', ''),
            'city': standard.get('City', 'Louisville'),
            'state': standard.get('StateOrProvince', 'KY'),
            'zip_code': standard.get('PostalCode', ''),
            'county': standard.get('CountyOrParish', ''),
            'subdivision': standard.get('SubdivisionName', ''),
            'latitude': standard.get('Latitude', 0),
            'longitude': standard.get('Longitude', 0),
            'list_price': standard.get('ListPrice', 0),
            'original_price': standard.get('OriginalListPrice', 0),
            'bedrooms': standard.get('BedsTotal', 0),
            'bathrooms_full': standard.get('BathsFull', 0),
            'bathrooms_half': standard.get('BathsHalf', 0),
            'sqft': standard.get('BuildingAreaTotal', 0),
            'lot_size': standard.get('LotSizeArea', 0),
            'year_built': standard.get('YearBuilt', 0),
            'description': standard.get('PublicRemarks', ''),
            'primary_photo_url': primary_photo,
            'photo_urls': photo_json,
            'listing_agent_name': standard.get('ListAgentName', ''),
            'listing_office': standard.get('ListOfficeName', ''),
            'last_synced': fields.Datetime.now(),
        }
        if existing:
            existing.write(vals)
        else:
            self.create(vals)

    @api.model
    def _cron_sync_listings(self):
        """Cron job to sync listings periodically"""
        _logger.info('Starting scheduled FlexMLS listing sync')
        self.action_sync_from_spark()
        _logger.info('Completed scheduled FlexMLS listing sync')