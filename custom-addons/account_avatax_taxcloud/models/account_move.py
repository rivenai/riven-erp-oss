# -*- coding: utf-8 -*-
# PES TaxCloud - account_move.py
# Override _get_line_data_for_external_taxes on account.move to bypass Avalara requirement
import logging
from odoo import models

_logger = logging.getLogger(__name__)

AVALARA_TO_TIC = {
    'PC': '20010', 'PF': '20010', 'SW': '30070',
    'SV': '30000', 'FR': '11010', 'NT': '00000',
}


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'

    def _get_taxcloud_tic_for_product(self, product):
        """Resolve a TIC code for a product, never raise."""
        default_tic = self.env['ir.config_parameter'].sudo().get_param(
            'taxcloud.default_tic', '20010'
        )
        if not default_tic or not str(default_tic).strip().isdigit():
            default_tic = '20010'
        default_tic = str(default_tic).strip().zfill(5)

        if not product:
            return default_tic
        # Try avatax_category_id if it exists
        avatax_cat = getattr(product, 'avatax_category_id', None)
        if not avatax_cat:
            _logger.info('TaxCloud: no avatax_category for "%s", using TIC=%s',
                         product.display_name, default_tic)
            return default_tic
        code = (avatax_cat.code or '').strip()
        if not code:
            return default_tic
        if code.isdigit():
            return code.zfill(5)
        mapped = AVALARA_TO_TIC.get(code[:2].upper())
        if mapped:
            return mapped
        _logger.info('TaxCloud: unmapped avatax code "%s" for "%s", using TIC=%s',
                     code, product.display_name, default_tic)
        return default_tic

    def _get_line_data_for_external_taxes(self):
        """Override account.move._get_line_data_for_external_taxes.

        Returns line data using TaxCloud TIC codes instead of requiring
        Avalara avatax_category_id. Compatible with the enterprise
        account_external_tax _compute_external_taxes caller signature.
        """
        res = []
        base_lines_data = self._get_rounded_base_and_tax_lines()
        if not base_lines_data:
            return res
        base_lines_values = [
            v for v in base_lines_data[0]
            if not v['record']._get_downpayment_lines()
        ]
        is_refund = self.move_type in ('out_refund', 'in_refund')
        for base_line in base_lines_values:
            record = base_line['record']
            product = getattr(record, 'product_id', None) or False
            tic = self._get_taxcloud_tic_for_product(product)
            subtotal = base_line['tax_details']['total_excluded_currency']
            company = self.company_id
            item_code = (
                f'UPC:{product.barcode}'
                if product and getattr(company, 'avalara_use_upc', False) and product.barcode
                else (product.default_code or str(product.id) if product else 'ITEM')
            )
            res.append({
                'base_line': base_line,
                'description': base_line.get('description') or record.name or '',
                # TaxCloud-specific extras stored on the dict
                'tic': tic,
                'amount': -subtotal if is_refund else subtotal,
                'qty': abs(base_line.get('quantity', 1)),
                'item_code': item_code,
                # Keep taxCode for any Avalara passthrough (won't raise)
                'taxCode': tic,
                'itemCode': item_code,
            })
        return res
