from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.auth_signup.controllers.main import AuthSignupHome


class PESDealerPortalHome(Home):
    """Override login page for id.pes.supply to render PES-branded template."""

    @http.route('/web/login', type='http', auth='none', sitemap=False)
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)
        # Inject portal name for template context
        if hasattr(response, 'qcontext'):
            response.qcontext.update({
                'pes_portal_name': 'PES Dealer Portal',
                'pes_tagline': 'Power. Electric. Solar. Supply.',
            })
        return response
