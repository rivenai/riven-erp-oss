{
    'name': 'PES Product Extensions',
    'version': '19.0.1.0.0',
    'author': 'Portlandia Electric Supply',
    'website': 'https://portlandiaelectricsupply.com',
    'summary': 'MPN, Brand, SKU, Tier, Status fields for PES',
    'description': 'Adds x_mpn, x_brand, x_manufacturer_id, x_pes_sku, x_tier, x_status, x_shopify_id to product.template and res.partner',
    'category': 'Inventory',
    'depends': ['product', 'purchase', 'stock'],
    'data': ['security/ir.model.access.csv'],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
