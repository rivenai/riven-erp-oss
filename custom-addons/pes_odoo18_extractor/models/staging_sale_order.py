# -*- coding: utf-8 -*-
"""Staging table for Odoo 18 sale.order + sale.order.line records."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StagingSaleOrder(models.Model):
    _name = 'pes.staging.sale.order'
    _description = 'Staged sale.order from Odoo 18'
    _order = 'o18_date_order desc'

    extraction_run_id = fields.Many2one(
        'pes.extraction.run', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)

    o18_id = fields.Integer(required=True, index=True)
    o18_model = fields.Char(default='sale.order', readonly=True)
    o18_write_date = fields.Datetime()

    name = fields.Char(index=True, help="O18 order name (SO0001, etc.)")
    state = fields.Char()
    partner_o18_id = fields.Integer()
    partner_name = fields.Char()
    o18_date_order = fields.Datetime()
    amount_untaxed = fields.Float(digits=(16, 2))
    amount_tax = fields.Float(digits=(16, 2))
    amount_total = fields.Float(digits=(16, 2))
    currency_code = fields.Char(default='USD')
    invoice_status = fields.Char()
    line_ids = fields.One2many('pes.staging.sale.order.line', 'order_id')
    line_count = fields.Integer(compute='_compute_line_count', store=True)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for r in self:
            r.line_count = len(r.line_ids)

    _sql_constraints = [
        ('o18_id_run_uniq',
         'unique(o18_id, extraction_run_id)',
         'Same Odoo 18 sale order appears twice in one run.'),
    ]

    @api.model
    def pull_from_o18(self, client, run):
        domain = []
        if run.cutoff_date:
            domain.append(('write_date', '>=', str(run.cutoff_date)))

        order_rows = client.search_read(
            'sale.order', domain,
            ['name', 'state', 'partner_id', 'date_order',
             'amount_untaxed', 'amount_tax', 'amount_total',
             'invoice_status', 'order_line', 'currency_id', 'write_date'],
        )
        _logger.info('staging_sale_order: got %s orders.', len(order_rows))

        # Pull all referenced lines in one shot
        line_ids = []
        for r in order_rows:
            line_ids.extend(r.get('order_line') or [])

        line_rows = []
        if line_ids:
            line_rows = client.search_read(
                'sale.order.line',
                [('id', 'in', line_ids)],
                ['order_id', 'product_id', 'name', 'product_uom_qty',
                 'price_unit', 'price_subtotal', 'price_total',
                 'qty_delivered', 'qty_invoiced', 'product_uom'],
            )

        # Index lines by order_id
        lines_by_order = {}
        for ln in line_rows:
            oid = ln.get('order_id') and ln['order_id'][0]
            if oid:
                lines_by_order.setdefault(oid, []).append(ln)

        created = 0
        for r in order_rows:
            order_vals = {
                'extraction_run_id': run.id,
                'o18_id': r['id'],
                'o18_write_date': r.get('write_date'),
                'name': r.get('name'),
                'state': r.get('state'),
                'partner_o18_id': r.get('partner_id') and r['partner_id'][0] or False,
                'partner_name': r.get('partner_id') and r['partner_id'][1] or False,
                'o18_date_order': r.get('date_order'),
                'amount_untaxed': r.get('amount_untaxed') or 0.0,
                'amount_tax': r.get('amount_tax') or 0.0,
                'amount_total': r.get('amount_total') or 0.0,
                'currency_code': (
                    r.get('currency_id') and r['currency_id'][1] or 'USD'
                ),
                'invoice_status': r.get('invoice_status'),
            }
            order_vals['line_ids'] = [
                (0, 0, {
                    'o18_id': ln['id'],
                    'product_o18_id': ln.get('product_id') and ln['product_id'][0] or False,
                    'product_name': ln.get('product_id') and ln['product_id'][1] or False,
                    'description': ln.get('name'),
                    'quantity': ln.get('product_uom_qty') or 0.0,
                    'price_unit': ln.get('price_unit') or 0.0,
                    'price_subtotal': ln.get('price_subtotal') or 0.0,
                    'price_total': ln.get('price_total') or 0.0,
                    'qty_delivered': ln.get('qty_delivered') or 0.0,
                    'qty_invoiced': ln.get('qty_invoiced') or 0.0,
                    'uom_name': ln.get('product_uom') and ln['product_uom'][1] or False,
                })
                for ln in lines_by_order.get(r['id'], [])
            ]
            self.create(order_vals)
            created += 1

        _logger.info('staging_sale_order: staged %s orders with %s lines.', created, len(line_rows))
        return created


class StagingSaleOrderLine(models.Model):
    _name = 'pes.staging.sale.order.line'
    _description = 'Staged sale.order.line from Odoo 18'
    _order = 'order_id, id'

    order_id = fields.Many2one(
        'pes.staging.sale.order', required=True, ondelete='cascade', index=True,
    )
    o18_id = fields.Integer(required=True, index=True)
    product_o18_id = fields.Integer()
    product_name = fields.Char()
    description = fields.Text()
    quantity = fields.Float(digits=(16, 4))
    price_unit = fields.Float(digits=(16, 4))
    price_subtotal = fields.Float(digits=(16, 2))
    price_total = fields.Float(digits=(16, 2))
    qty_delivered = fields.Float(digits=(16, 4))
    qty_invoiced = fields.Float(digits=(16, 4))
    uom_name = fields.Char()
