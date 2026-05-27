from odoo import models

class View(models.Model):
    _inherit = 'ir.ui.view'

    def _render_template(self, template, values=None):
        if values is None:
            values = {}
        values['riven_erp_brand'] = 'Riven ERP'
        values['riven_erp_url'] = 'https://rivenai.io/rivenerp'
        return super()._render_template(template, values)
