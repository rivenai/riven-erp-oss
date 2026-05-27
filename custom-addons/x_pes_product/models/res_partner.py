from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_brand = fields.Char(string='Brand Name')
    x_tier = fields.Integer(string='Vendor Tier', default=0)
    x_mpn_prefix = fields.Char(string='MPN Prefix')
