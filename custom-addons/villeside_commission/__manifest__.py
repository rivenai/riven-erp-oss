{
    'name': 'Villeside Commission Tracking',
    'version': '19.0.1.0.0',
    'category': 'Real Estate',
    'summary': 'Commission split plans, cap tracking, and agent payout management',
    'author': 'Villeside Realty LLC',
    'website': 'https://villeside.cassilly.capital',
    'license': 'LGPL-3',
    'depends': ['base', 'crm', 'account', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/commission_plan_views.xml',
        'views/commission_line_views.xml',
        'views/commission_menus.xml',
        'data/commission_plan_data.xml',
    ],
    'installable': True,
    'application': True,
}