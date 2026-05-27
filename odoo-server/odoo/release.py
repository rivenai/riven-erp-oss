# Part of Odoo. See LICENSE file for full copyright and licensing details.

RELEASE_LEVELS = [ALPHA, BETA, RELEASE_CANDIDATE, FINAL] = ['alpha', 'beta', 'candidate', 'final']
RELEASE_LEVELS_DISPLAY = {ALPHA: 'a',
                          BETA: 'b',
                          RELEASE_CANDIDATE: 'rc',
                          FINAL: ''}

# version_info format: (MAJOR, MINOR, MICRO, RELEASE_LEVEL, SERIAL)
# inspired by Python's own sys.version_info, in order to be
# properly comparable using normal operators, for example:
#  (6,1,0,'beta',0) < (6,1,0,'candidate',1) < (6,1,0,'candidate',2)
#  (6,1,0,'candidate',2) < (6,1,0,'final',0) < (6,1,2,'final',0)
# NOTE: during release, the MAJOR version can become an arbitrary string ('saas~xx')
version_info = (19, 0, 0, FINAL, 0, '')
series = serie = major_version = '.'.join(str(s) for s in version_info[:2])
version = series + RELEASE_LEVELS_DISPLAY[version_info[3]] + str(version_info[4] or '') + version_info[5]

description = 'Riven ERP Server'
long_desc = '''Riven ERP is a complete ERP and CRM. The main features are accounting (analytic
and financial), stock management, sales and purchases management, tasks
automation, marketing campaigns, help desk, POS, etc. Technical features include
a distributed server, an object database, a dynamic GUI,
customizable reports, and XML-RPC interfaces.
'''
classifiers = """Development Status :: 5 - Production/Stable
License :: OSI Approved :: GNU Lesser General Public License v3

Programming Language :: Python
"""
url = 'https://www.rivenai.io'
author = 'Riven AI'
author_email = 'support@rivenai.io'
license = 'LGPL-3'

nt_service_name = "riven-erp-server-" + series.replace('~','-')

MIN_PY_VERSION = (3, 10)
MAX_PY_VERSION = (3, 13)
MIN_PG_VERSION = 13

version += '-20260123'

repos_heads = {'odoo': '85fad094a4bdf46d7aefc749d9297f9c21f0e195', 'enterprise': 'a96759c65e1af6d55d9eb1fe818547ffca2d0c5a', 'design-themes': 'c8a9bb44191bab7360c968e81447448028b0fd78'}

# Riven ERP branding override
product_name = 'Riven ERP'
