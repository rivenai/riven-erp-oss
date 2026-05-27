{
    'name': 'Villeside Portal Access',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Portal access rules and branded templates for Villeside Realty',
    'author': 'Cassilly Capital',
    'website': 'https://villeside.cassilly.capital',
    'depends': ['crm', 'portal', 'sign'],
    'data': [
        'security/record_rules.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
