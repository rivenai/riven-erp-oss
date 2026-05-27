from odoo import http
from odoo.http import request


class ListingController(http.Controller):

    @http.route('/listings', type='http', auth='public', website=True)
    def listings_index(self, search=None, property_type=None, min_price=None, max_price=None, bedrooms=None, **kwargs):
        domain = [('website_published', '=', True), ('mls_status', '=', 'active')]
        if search:
            domain += ['|', '|',
                       ('street_address', 'ilike', search),
                       ('city', 'ilike', search),
                       ('mls_id', 'ilike', search)]
        if property_type:
            domain += [('property_type', '=', property_type)]
        if min_price:
            domain += [('list_price', '>=', float(min_price))]
        if max_price:
            domain += [('list_price', '<=', float(max_price))]
        if bedrooms:
            domain += [('bedrooms', '>=', int(bedrooms))]

        listings = request.env['flexmls.listing'].sudo().search(domain, order='list_price desc', limit=50)
        return request.render('villeside_flexmls.listings_index', {
            'listings': listings,
            'search': search,
        })

    @http.route('/listings/<int:listing_id>', type='http', auth='public', website=True)
    def listing_detail(self, listing_id, **kwargs):
        listing = request.env['flexmls.listing'].sudo().browse(listing_id)
        if not listing.exists() or not listing.website_published:
            return request.redirect('/listings')
        return request.render('villeside_flexmls.listing_detail', {
            'listing': listing,
        })