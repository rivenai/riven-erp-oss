{
    'name': 'PES Dealer Portal',
    'version': '19.0.1.0.0',
    'summary': 'Portlandia Electric Supply - Branded Dealer Login & Portal',
    'description': 'Custom branding for id.pes.supply dealer portal. Modeled after Generac360 UX with PES brand colors (navy #1a2332, green #2db35d, white).',
    'category': 'Website',
    'author': 'Portlandia Electric Supply',
    'website': 'https://id.pes.supply',
    'license': 'LGPL-3',
    'depends': ['website', 'portal', 'auth_signup', 'web'],
    'data': [
        'views/login_template.xml',
        'views/portal_layout.xml',
        'views/website_assets.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            'pes_dealer_portal/static/src/css/pes_variables.scss',
        ],
        'web.assets_frontend': [
            'pes_dealer_portal/static/src/css/pes_dealer_portal.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
