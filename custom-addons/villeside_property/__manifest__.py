{
    'name': 'Villeside Property Listings',
    'version': '19.0.1.0.0',
    'category': 'Real Estate',
    'summary': 'Property listing management with MLS integration, photos, and status workflows',
    'author': 'Villeside Realty LLC',
    'website': 'https://villeside.cassilly.capital',
    'license': 'LGPL-3',
    'depends': ['base', 'crm', 'website', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/property_views.xml',
        'views/property_menus.xml',
        'data/property_type_data.xml',
    ],
    'installable': True,
    'application': True,
}