{
    'name': 'Villeside FlexMLS Integration',
    'version': '19.0.1.0.0',
    'category': 'Real Estate',
    'summary': 'FlexMLS/Spark API integration for live MLS property listings',
    'description': """
        Connects Odoo to the FBS Spark API (FlexMLS) for IDX/VOW data.
        Syncs active MLS listings to the website with search, filters,
        detail pages, photos, maps, and automated refresh.
    """,
    'author': 'Villeside Realty LLC',
    'website': 'https://villesiderealty.cassilly.capital',
    'license': 'LGPL-3',
    'depends': ['base', 'website', 'crm', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/flexmls_cron.xml',
        'views/flexmls_listing_views.xml',
        'views/flexmls_config_views.xml',
        'views/website_listing_templates.xml',
        'views/menus.xml',
                'views/assets.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'villeside_flexmls/static/src/css/listings.css',
                        'villeside_flexmls/static/src/css/brand.css',
            'villeside_flexmls/static/src/js/listing_search.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}