{
    'name': 'Villeside CRM Stages',
    'version': '19.0.1.0.0',
    'category': 'CRM',
    'summary': 'Company-specific CRM pipeline stages for Villeside Realty and all Cassilly Capital entities',
    'author': 'Cassilly Capital',
    'website': 'https://villeside.cassilly.capital',
    'depends': ['crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/crm_stages_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
