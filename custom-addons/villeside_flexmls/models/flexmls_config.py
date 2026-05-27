from odoo import api, fields, models, _


class FlexmlsConfig(models.Model):
    _name = 'flexmls.config'
    _description = 'FlexMLS API Configuration'
    _rec_name = 'name'

    name = fields.Char('Config Name', default='Default', required=True)
    api_key = fields.Char('Spark API Key', required=True)
    api_secret = fields.Char('Spark API Secret')
    access_token = fields.Char('Access Token')
    api_base_url = fields.Char('API Base URL', default='https://sparkapi.com/v1')
    mls_id = fields.Char('MLS ID', help='Your MLS identifier')
    sync_interval = fields.Integer('Sync Interval (hours)', default=6)
    last_sync = fields.Datetime('Last Successful Sync')
    active = fields.Boolean('Active', default=True)
    auto_publish = fields.Boolean('Auto-publish Listings', default=True)
    default_property_types = fields.Char(
        'Default Property Types',
        default='Residential,Condo,Multi-Family',
        help='Comma-separated list of property types to sync',
    )
    geo_filter = fields.Char(
        'Geographic Filter',
        help='SparkQL filter for geography, e.g. City Eq Louisville',
    )

    @api.model
    def get_config(self):
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            config = self.create({'name': 'Default'})
        return config