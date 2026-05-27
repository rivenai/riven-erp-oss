# -*- coding: utf-8 -*-
"""Staging table for Odoo 18 product.product records."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

O18_PRODUCT_FIELDS = [
    'name', 'display_name', 'default_code', 'barcode', 'type',
    'list_price', 'standard_price', 'uom_id', 'uom_po_id',
    'categ_id', 'product_tmpl_id', 'active',
    'create_date', 'write_date',
]


class StagingProduct(models.Model):
    _name = 'pes.staging.product'
    _description = 'Staged product.product from Odoo 18'
    _order = 'o18_id'

    extraction_run_id = fields.Many2one(
        'pes.extraction.run', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)

    o18_id = fields.Integer(required=True, index=True)
    o18_model = fields.Char(default='product.product', readonly=True)
    o18_write_date = fields.Datetime()
    o18_active = fields.Boolean()

    name = fields.Char()
    display_name = fields.Char()
    default_code = fields.Char(index=True)
    barcode = fields.Char()
    product_type = fields.Char()
    list_price = fields.Float(digits=(16, 4))
    standard_price = fields.Float(digits=(16, 4))
    uom_name = fields.Char()
    uom_po_name = fields.Char()
    category_name = fields.Char()
    product_tmpl_o18_id = fields.Integer()

    promoted_product_id = fields.Many2one('product.product')
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
         'Same Odoo 18 product appears twice in one run.'),
    ]

    @api.model
    def pull_from_o18(self, client, run):
        domain = [('active', 'in', [True, False])]
        if run.cutoff_date:
            domain.append(('write_date', '>=', str(run.cutoff_date)))

        rows = client.search_read('product.product', domain, O18_PRODUCT_FIELDS)
        _logger.info('staging_product: got %s rows.', len(rows))

        vals_list = [{
            'extraction_run_id': run.id,
            'o18_id': r['id'],
            'o18_write_date': r.get('write_date'),
            'o18_active': r.get('active'),
            'name': r.get('name'),
            'display_name': r.get('display_name'),
            'default_code': r.get('default_code'),
            'barcode': r.get('barcode'),
            'product_type': r.get('type'),
            'list_price': r.get('list_price') or 0.0,
            'standard_price': r.get('standard_price') or 0.0,
            'uom_name': r.get('uom_id') and r['uom_id'][1] or False,
            'uom_po_name': r.get('uom_po_id') and r['uom_po_id'][1] or False,
            'category_name': r.get('categ_id') and r['categ_id'][1] or False,
            'product_tmpl_o18_id': r.get('product_tmpl_id') and r['product_tmpl_id'][0] or False,
        } for r in rows]

        BATCH = 500
        created = 0
        for i in range(0, len(vals_list), BATCH):
            self.create(vals_list[i:i + BATCH])
            created += len(vals_list[i:i + BATCH])
        return created
