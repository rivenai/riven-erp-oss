import json, re
from odoo import http
from odoo.http import request
API_KEY = 'Gd82jF93kL0pXr91Zz9qUw45Nv7YmQ2t'
def norm(n): return re.sub(r'[^0-9+]','',str(n or ''))
class ThreeCX(http.Controller):
    @http.route('/api/3cx/crm',type='json',auth='none',methods=['POST'],csrf=False)
    def lookup(self,**kw):
        d=json.loads(request.httprequest.data)
        if d.get('apikey','')!=API_KEY: return {'error':'bad key'}
        n=norm(d.get('number',''))
        if not n: return {'error':'no number'}
        p=request.env['res.partner'].sudo().search(['|','|','|',('phone','ilike',n[-10:]),('mobile','ilike',n[-10:]),('phone','ilike',d['number']),('mobile','ilike',d['number'])],limit=1)
        if not p: return {}
        nm=(p.name or '').split(' ',1)
        return {'partner_id':p.id,'first':nm[0],'email':p.email or '','mobile':p.mobile or '','url':'/odoo/contacts/%d'%p.id,'firstname':nm[0],'lastname':nm[1] if len(nm)>1 else '','phone':p.phone or '','name':p.name or ''}
