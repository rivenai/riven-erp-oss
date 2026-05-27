# -*- coding: utf-8 -*-
# PES TaxCloud Client - avatax_client.py
import logging
import requests

_logger = logging.getLogger(__name__)


class AvaTaxClient:
    """TaxCloud API client replacing Avalara AvaTax."""

    def __init__(self, company):
        self.company = company
        env = getattr(company, 'env', None)
        if env:
            get_param = env['ir.config_parameter'].sudo().get_param
        else:
            get_param = lambda k, d='': d
        self.api_id = get_param('taxcloud.api_id', '')
        self.api_key = get_param('taxcloud.api_key', '')

    def _auth(self):
        return {
            'apiLoginID': self.api_id,
            'apiKey': self.api_key,
        }

    def _headers(self):
        return {'Content-Type': 'application/json'}

    def _build_payload(self, partner, lines, doc_code):
        """Build TaxCloud Lookup payload."""
        z = (partner.zip or '00000').replace('-', '').replace(' ', '')
        origin_city = self.company.city or 'Portland'
        origin_state = self.company.state_id.code or 'OR'
        origin_zip = (self.company.zip or '97201')[:5].zfill(5)
        origin_street = self.company.street or ''
        dest_city = partner.city or ''
        dest_state = partner.state_id.code if partner.state_id else ''
        dest_street = partner.street or ''
        return {
            **self._auth(),
            'customerID': str(partner.id),
            'cartID': doc_code or 'pes',
            'origin': {
                'Address1': origin_street,
                'City': origin_city,
                'State': origin_state,
                'Zip5': origin_zip,
                'Zip4': '0000'
            },
            'destination': {
                'Address1': dest_street,
                'City': dest_city,
                'State': dest_state,
                'Zip5': z[:5].zfill(5),
                'Zip4': '0000'
            },
            'cartItems': [
                {
                    'Index': i,
                    'ItemID': str(i),
                    'TIC': line.get('tic', '20010'),
                    'Price': float(line.get('amount', 0)),
                    'Qty': float(line.get('qty', 1)),
                    'deliveredBySeller': False
                }
                for i, line in enumerate(lines)
            ],
            'deliveredBySeller': False
        }

    def calculate_tax_per_line(self, partner, lines, doc_code=None):
        """Call TaxCloud Lookup and return per-line tax amounts."""
        if not self.api_id:
            _logger.warning('TaxCloud: No API ID configured')
            return {'tax_amount': 0.0, 'per_line_tax': [{'TaxAmount': 0.0} for _ in lines]}

        z = (partner.zip or '00000').replace('-', '').replace(' ', '')
        dest_city = partner.city or ''
        dest_state = partner.state_id.code if partner.state_id else ''
        payload = self._build_payload(partner, lines, doc_code)

        _logger.info(
            'TaxCloud Lookup: customer=%s (%s), dest=%s %s %s, items=%d, doc=%s',
            partner.name, partner.id, dest_city, dest_state, z[:5], len(lines), doc_code
        )

        try:
            r = requests.post(
                'https://api.taxcloud.net/1.0/TaxCloud/Lookup',
                json=payload,
                headers=self._headers(),
                timeout=10
            )
            d = r.json()
            response_type = d.get('ResponseType')
            messages = d.get('Messages', [])

            if response_type != 3:
                error_msgs = [m.get('Message', '') for m in messages]
                _logger.error(
                    'TaxCloud Lookup FAILED: ResponseType=%s, Messages=%s, '
                    'customer=%s, dest=%s %s %s',
                    response_type, error_msgs, partner.name, dest_city, dest_state, z[:5]
                )
                return {
                    'tax_amount': 0.0,
                    'per_line_tax': [{'TaxAmount': 0.0} for _ in lines]
                }

            cart_items = d.get('CartItemsResponse', [])
            total = sum(float(it.get('TaxAmount', 0)) for it in cart_items)

            _logger.info(
                'TaxCloud Lookup SUCCESS: customer=%s, dest=%s %s, total_tax=%.2f',
                partner.name, dest_city, dest_state, total
            )

            # Build per-line tax list aligned to input lines
            # CartItemsResponse items have 'CartItemIndex' matching our 'Index'
            per_line = [{'TaxAmount': 0.0} for _ in lines]
            for item in cart_items:
                idx = item.get('CartItemIndex', -1)
                if 0 <= idx < len(per_line):
                    per_line[idx] = {'TaxAmount': float(item.get('TaxAmount', 0.0))}

            return {'tax_amount': total, 'per_line_tax': per_line}

        except Exception as e:
            _logger.exception(
                'TaxCloud Lookup EXCEPTION: customer=%s, dest=%s %s %s: %s',
                partner.name, dest_city, dest_state, z[:5], str(e)
            )
            return {
                'tax_amount': 0.0,
                'per_line_tax': [{'TaxAmount': 0.0} for _ in lines]
            }

    def calculate_tax(self, partner, lines, doc_code=None):
        """Legacy method - calls calculate_tax_per_line."""
        result = self.calculate_tax_per_line(partner, lines, doc_code=doc_code)
        return {
            'tax_amount': result['tax_amount'],
            'tax_rate': 0.0,
            'lines': result['per_line_tax'],
        }

    def avalara_commit(self, doc_code):
        return True

    def avalara_void(self, doc_code):
        return True

    def ping(self):
        return True
