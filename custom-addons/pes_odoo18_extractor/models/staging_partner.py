# -*- coding: utf-8 -*-
"""
Staging table for Odoo 18 res.partner records.

Pulls customers + vendors. Tags vendors as 'manufacturer' if they have any
product.supplierinfo references, supporting the 229 manufacturer scorecard.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Fields we ask Odoo 18 for. Conservative list — extend as needed.
O18_PARTNER_FIELDS = [
    'name', 'display_name', 'email', 'phone', 'mobile', 'website',
    'street', 'street2', 'city', 'zip', 'country_id', 'state_id',
    'vat', 'company_type', 'is_company', 'parent_id',
    'customer_rank', 'supplier_rank', 'ref',
    'commercial_partner_id', 'category_id',
    'create_date', 'write_date',
]


class StagingPartner(models.Model):
    _name = 'pes.staging.partner'
    _description = 'Staged res.partner from Odoo 18'
    _order = 'o18_id'

    extraction_run_id = fields.Many2one(
        'pes.extraction.run', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)

    # Traceability
    o18_id = fields.Integer(required=True, index=True)
    o18_model = fields.Char(default='res.partner', readonly=True)
    o18_write_date = fields.Datetime()

    # Mirror fields
    name = fields.Char()
    display_name = fields.Char()
    email = fields.Char()
    phone = fields.Char()
    mobile = fields.Char()
    website = fields.Char()
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    zip = fields.Char()
    country_code = fields.Char()
    state_code = fields.Char()
    vat = fields.Char()
    company_type = fields.Char()
    is_company = fields.Boolean()
    parent_o18_id = fields.Integer()
    commercial_partner_o18_id = fields.Integer()
    customer_rank = fields.Integer()
    supplier_rank = fields.Integer()
    ref = fields.Char()
    category_names = fields.Char()

    # Forensic flags
    is_vendor = fields.Boolean(compute='_compute_role_flags', store=True)
    is_customer = fields.Boolean(compute='_compute_role_flags', store=True)
    is_manufacturer_candidate = fields.Boolean(
        help="True if this vendor has product.supplierinfo lines (229 manufacturer pool)."
    )

    # Promotion tracking
    promoted_partner_id = fields.Many2one(
        'res.partner',
        help="If this staged record has been promoted to a live partner, the link.",
    )
    promotion_state = fields.Selection(
        [('staged', 'Staged'),
         ('reviewed', 'Reviewed'),
         ('promoted', 'Promoted'),
         ('skipped', 'Skipped')],
        default='staged',
    )

    _sql_constraints = [
        ('o18_id_run_uniq',
         'unique(o18_id, extraction_run_id)',
         'Same Odoo 18 partner appears twice in one run.'),
    ]

    @api.depends('customer_rank', 'supplier_rank')
    def _compute_role_flags(self):
        for rec in self:
            rec.is_customer = (rec.customer_rank or 0) > 0
            rec.is_vendor = (rec.supplier_rank or 0) > 0

    # ------------------------------------------------------------------
    # Pull from Odoo 18
    # ------------------------------------------------------------------
    @api.model
    def pull_from_o18(self, client, run):
        """Fetch all partners from Odoo 18 + (optional) supplier-info delta.

        Returns count of records staged.
        """
        domain = [('active', 'in', [True, False])]
        if run.cutoff_date:
            domain.append(('write_date', '>=', str(run.cutoff_date)))

        _logger.info('staging_partner: fetching from Odoo 18 with domain=%s', domain)
        rows = client.search_read(
            'res.partner', domain, O18_PARTNER_FIELDS,
        )
        _logger.info('staging_partner: got %s rows from Odoo 18.', len(rows))

        # Find vendors with supplierinfo records (manufacturer candidates)
        manufacturer_ids = set()
        if rows:
            vendor_o18_ids = [r['id'] for r in rows if (r.get('supplier_rank') or 0) > 0]
            if vendor_o18_ids:
                try:
                    si = client.search_read(
                        'product.supplierinfo',
                        [('partner_id', 'in', vendor_o18_ids)],
                        ['partner_id'], limit=10000,
                    )
                    manufacturer_ids = {
                        x['partner_id'][0] for x in si if x.get('partner_id')
                    }
                except Exception as e:
                    _logger.warning(
                        'staging_partner: supplierinfo lookup failed (%s) — '
                        'manufacturer flag will be empty.', e,
                    )

        vals_list = []
        for r in rows:
            vals_list.append({
                'extraction_run_id': run.id,
                'o18_id': r['id'],
                'o18_write_date': r.get('write_date'),
                'name': r.get('name'),
                'display_name': r.get('display_name'),
                'email': r.get('email'),
                'phone': r.get('phone'),
                'mobile': r.get('mobile'),
                'website': r.get('website'),
                'street': r.get('street'),
                'street2': r.get('street2'),
                'city': r.get('city'),
                'zip': r.get('zip'),
                'country_code': r.get('country_id') and r['country_id'][1] or False,
                'state_code': r.get('state_id') and r['state_id'][1] or False,
                'vat': r.get('vat'),
                'company_type': r.get('company_type'),
                'is_company': r.get('is_company'),
                'parent_o18_id': r.get('parent_id') and r['parent_id'][0] or False,
                'commercial_partner_o18_id': (
                    r.get('commercial_partner_id') and r['commercial_partner_id'][0] or False
                ),
                'customer_rank': r.get('customer_rank') or 0,
                'supplier_rank': r.get('supplier_rank') or 0,
                'ref': r.get('ref'),
                'category_names': ', '.join(c[1] for c in (r.get('category_id') or [])) or False,
                'is_manufacturer_candidate': r['id'] in manufacturer_ids,
            })

        # Batch insert
        BATCH = 500
        created = 0
        for i in range(0, len(vals_list), BATCH):
            chunk = vals_list[i:i + BATCH]
            self.create(chunk)
            created += len(chunk)
            _logger.info('staging_partner: staged %s/%s', created, len(vals_list))

        return created
