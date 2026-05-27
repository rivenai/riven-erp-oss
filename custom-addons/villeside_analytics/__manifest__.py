{
    'name': 'Villeside Real Estate Analytics',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Agent performance, market data, pipeline analytics',
    'author': 'Villeside Realty / Cassilly Capital',
    'website': 'https://villesiderealty.com',
    'depends': ['crm', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/analytics_views.xml',
        'views/analytics_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}