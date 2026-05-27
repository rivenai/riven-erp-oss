{
    'name': 'Villeside Transaction Management',
    'version': '19.0.1.0.0',
    'category': 'Real Estate',
    'summary': 'End-to-end transaction workflow from offer to closing with compliance checklists',
    'author': 'Villeside Realty LLC',
    'website': 'https://villeside.cassilly.capital',
    'license': 'LGPL-3',
    'depends': ['base', 'crm', 'mail', 'villeside_property', 'villeside_commission'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/checklist_template_data.xml',
        'views/transaction_views.xml',
        'views/transaction_menus.xml',
    ],
    'installable': True,
    'application': True,
}