# -*- coding: utf-8 -*-
# PES TaxCloud Integration - account_external_tax_mixin.py v3
# Complete override of Avalara enterprise to use TaxCloud API
import logging
from odoo import models, api, Command
from odoo.addons.account_avatax_taxcloud.models.avatax_client import AvaTaxClient

_logger = logging.getLogger(__name__)

AVALARA_TO_TIC = {
    'PC': '20010',
    'PF': '20010',
    'SW': '30070',
    'SV': '30000',
    'FR': '11010',
    'NT': '00000',
}


class AccountExternalTaxMixin(models.AbstractModel):
    _inherit = 'account.external.tax.mixin'

    def _get_taxcloud_default_tic(self):
        tic = self.env['ir.config_parameter'].sudo().get_param(
            'taxcloud.default_tic', '20010'
        )
        if not tic or not str(tic).strip().isdigit():
            tic = '20010'
        return str(tic).strip().zfill(5)

    def _resolve_tic_code(self, product):
        """Map product to TIC code, never raise."""
        default_tic = self._get_taxcloud_default_tic()
        if not product:
            return default_tic
        avatax_cat = getattr(product, 'avatax_category_id', None)
        if not avatax_cat:
            return default_tic
        code = (avatax_cat.code or '').strip()
        if not code:
            return default_tic
        if code.isdigit():
            return code.zfill(5)
        mapped = AVALARA_TO_TIC.get(code[:2].upper())
        return mapped if mapped else default_tic

    def _prepare_avatax_document_line_service_call(self, line_data, is_refund):
        """Override: Safe access to tax_details, use TIC code."""
        base_line = line_data['base_line']
        record = base_line.get('record')
        product = getattr(record, 'product_id', False) if record else False
        tic = self._resolve_tic_code(product)
        company = self.company_id if hasattr(self, 'company_id') else (
            record.company_id if record and hasattr(record, 'company_id') else False
        )
        if product and company and getattr(company, 'avalara_use_upc', False) and getattr(product, 'barcode', None):
            item_code = f'UPC:{product.barcode}'
        elif product:
            item_code = getattr(product, 'default_code', None) or str(product.id)
        else:
            item_code = 'ITEM'
        # Safe access: tax_details may not have total_excluded_currency
        tax_details = base_line.get('tax_details') or {}
        subtotal = (
            tax_details.get('total_excluded_currency')
            or tax_details.get('total_excluded')
            or base_line.get('price_subtotal')
            or 0.0
        )
        if subtotal is None:
            subtotal = 0.0
        description = ''
        if record:
            description = getattr(record, 'name', '') or ''
        record_name = record._name if record else 'unknown'
        record_id = base_line.get('id', 0)
        return {
            'amount': -subtotal if is_refund else subtotal,
            'description': description,
            'quantity': abs(base_line.get('quantity', 1)),
            'taxCode': tic,
            'itemCode': item_code,
            'number': '%s,%s' % (record_name, record_id),
        }

    def _get_external_taxes(self):
        """Override enterprise _get_external_taxes to use TaxCloud instead of Avalara."""
        # Handle non-avatax records via super()
        non_avatax = self.filtered(lambda r: not r.is_avatax)
        res = super(AccountExternalTaxMixin, non_avatax)._get_external_taxes() if non_avatax else {}

        for company, records in self.filtered('is_avatax').grouped('company_id').items():
            base_line_with_tax_values = []
            client = AvaTaxClient(company)

            for record in records:
                try:
                    service_params = record._get_avatax_service_params()
                except Exception as e:
                    _logger.warning('TaxCloud: _get_avatax_service_params failed: %s', e)
                    continue

                line_data_list = service_params.get('line_data', [])
                if not line_data_list:
                    _logger.info('TaxCloud: No line_data for %s, skipping', record.display_name)
                    continue

                partner = service_params.get('shipping_partner') or service_params.get('commercial_partner')
                doc_code = service_params.get('unique_code') or record.name or 'pes'
                is_refund = service_params.get('is_refund', False) or False
                fiscal_position = service_params.get('fiscal_position')

                if not partner:
                    _logger.warning('TaxCloud: No partner for %s, skipping', record.display_name)
                    continue

                # Build TaxCloud lines
                taxcloud_lines = []
                base_lines = []
                for ld in line_data_list:
                    try:
                        prepared = record._prepare_avatax_document_line_service_call(ld, is_refund)
                        base_line = ld['base_line']
                        base_lines.append(base_line)
                        taxcloud_lines.append({
                            'tic': prepared.get('taxCode', '20010'),
                            'amount': abs(float(prepared.get('amount', 0))),
                            'qty': float(prepared.get('quantity', 1)),
                        })
                    except Exception as e:
                        _logger.warning('TaxCloud: Error preparing line for %s: %s', record.display_name, e)
                        base_lines.append(ld.get('base_line', {}))
                        taxcloud_lines.append({'tic': '20010', 'amount': 0.0, 'qty': 1.0})

                if not taxcloud_lines:
                    continue

                # Call TaxCloud API
                result = client.calculate_tax_per_line(partner, taxcloud_lines, doc_code=doc_code)
                per_line_taxes = result.get('per_line_tax', [])
                total_tax = result.get('tax_amount', 0.0)

                _logger.info(
                    'TaxCloud: doc=%s partner=%s total_tax=%.2f lines=%d',
                    doc_code, getattr(partner, 'name', str(partner)), total_tax, len(per_line_taxes)
                )

                # Get tax account from fiscal position (enterprise field)
                invoice_account_id = False
                refund_account_id = False
                if fiscal_position:
                    invoice_account_id = getattr(fiscal_position, 'avatax_invoice_account_id', False)
                    refund_account_id = getattr(fiscal_position, 'avatax_refund_account_id', False)
                    if invoice_account_id:
                        invoice_account_id = invoice_account_id.id
                    if refund_account_id:
                        refund_account_id = refund_account_id.id

                # Build base_line_with_tax_values in format _process_external_taxes expects
                for i, (base_line, line_tax) in enumerate(zip(base_lines, per_line_taxes)):
                    if not base_line:
                        continue
                    tax_amount = float(line_tax.get('TaxAmount', 0.0))
                    subtotal = abs(float(taxcloud_lines[i].get('amount', 0.0))) or 1.0
                    rate = (tax_amount / subtotal * 100) if subtotal else 0.0

                    # Build tax values 3-tuple: (tax_group_vals, tax_vals, tax_amounts)
                    tax_group_vals = {
                        'name': 'State and Local Tax',
                        'company_id': company.id,
                    }
                    repartition_invoice = [
                        Command.create({'repartition_type': 'base'}),
                        Command.create({'repartition_type': 'tax', 'account_id': invoice_account_id}) if invoice_account_id
                        else Command.create({'repartition_type': 'tax'}),
                    ]
                    repartition_refund = [
                        Command.create({'repartition_type': 'base'}),
                        Command.create({'repartition_type': 'tax', 'account_id': refund_account_id}) if refund_account_id
                        else Command.create({'repartition_type': 'tax'}),
                    ]
                    tax_vals = {
                        'name': 'State and Local Tax %.4g%%' % rate,
                        'company_id': company.id,
                        'amount': rate,
                        'amount_type': 'percent',
                        'invoice_repartition_line_ids': repartition_invoice,
                        'refund_repartition_line_ids': repartition_refund,
                    }
                    tax_amount_currency = tax_amount * (-1 if is_refund else 1)
                    tax_amounts = {'tax_amount_currency': tax_amount_currency}

                    tax_values_list = [(tax_group_vals, tax_vals, tax_amounts)] if tax_amount != 0.0 else []
                    base_line_with_tax_values.append((base_line, tax_values_list))

            if base_line_with_tax_values:
                res.update(self._process_external_taxes(company, base_line_with_tax_values, 'name'))

        return res
