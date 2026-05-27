from . import models

def _post_init_hook(env):
    env['ir.config_parameter'].set_param('web.base.url', 'https://erp.rivenai.io')
    env.cr.commit()
