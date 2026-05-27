from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_mpn = fields.Char(string='MPN', index=True, help='Manufacturer Part Number')
    x_brand = fields.Char(string='Brand', index=True)
    x_manufacturer_id = fields.Many2one('res.partner', string='Manufacturer',
        domain="[('is_company','=',True)]", index=True)
    x_pes_sku = fields.Char(string='PES SKU', index=True)
    x_tier = fields.Integer(string='Vendor Tier', default=0)
    x_status = fields.Selection([
        ('active','Active'),
        ('deprecated','Deprecated'),
        ('call_now','Call Now'),
        ('buy_now','Buy Now'),
        ('superseded','Superseded'),
    ], string='Product Status', default='active', index=True)
    x_superseded_by = fields.Many2one('product.template', string='Superseded By')
    x_shopify_id = fields.Char(string='Shopify Product ID', index=True)
    x_shopify_handle = fields.Char(string='Shopify Handle')
    x_shopify_synced = fields.Datetime(string='Last Shopify Sync')
