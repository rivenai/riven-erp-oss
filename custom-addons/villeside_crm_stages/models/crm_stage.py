from odoo import models, fields, api


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    company_id = fields.Many2one(
        'res.company', string='Company',
        help='If set, this stage is only visible for this company.',
    )
    pipeline_type = fields.Selection([
        ('residential_buyer', 'Residential - Buyer'),
        ('residential_seller', 'Residential - Seller/Listing'),
        ('commercial', 'Commercial (CRE)'),
        ('property_mgmt', 'Property Management'),
        ('it_msp', 'IT / MSP Services'),
        ('logistics', 'Logistics / Freight'),
        ('wholesale', 'Wholesale / B2B'),
    ], string='Pipeline Type', default='residential_buyer')

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Filter stages by current company when company_id is set."""
        company_domain = [
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.env.company.id),
        ]
        return super()._search(
            domain + company_domain,
            offset=offset, limit=limit, order=order
        )
