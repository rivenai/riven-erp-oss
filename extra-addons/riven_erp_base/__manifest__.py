{
    'name': 'Riven ERP Base',
    'version': '19.0.1.0.0',
    'author': 'Riven AI',
    'website': 'https://rivenai.io',
    'category': 'Hidden',
    'summary': 'Riven ERP branding and base configuration',
    'description': '''
        Base module for Riven ERP. Replaces Odoo branding with Riven ERP identity.
    ''',
    'depends': ['web', 'base_setup'],
    'data': [],
    'installable': True,
    'auto_install': True,
    'license': 'LGPL-3',
    'post_init_hook': '_post_init_hook',
}
