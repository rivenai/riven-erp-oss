from odoo import models, fields, api
from datetime import datetime, timedelta
import hashlib
import uuid
import logging

_logger = logging.getLogger(__name__)


class EsignDocument(models.Model):
    _name = 'villeside.esign.document'
    _description = 'E-Signature Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Document Name', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent for Signature'),
        ('partially_signed', 'Partially Signed'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    document_type = fields.Selection([
        ('purchase_agreement', 'Purchase Agreement'),
        ('listing_agreement', 'Listing Agreement'),
        ('lease', 'Lease Agreement'),
        ('addendum', 'Addendum'),
        ('disclosure', 'Disclosure'),
        ('inspection', 'Inspection Report'),
        ('closing', 'Closing Documents'),
        ('amendment', 'Amendment'),
        ('counteroffer', 'Counter Offer'),
        ('other', 'Other'),
    ], string='Document Type', required=True)
    template_id = fields.Many2one('villeside.esign.template', string='Template')
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    signer_ids = fields.One2many('villeside.esign.signer', 'document_id', string='Signers')
    lead_id = fields.Many2one('crm.lead', string='Related Lead')
    transaction_id = fields.Many2one('villeside.transaction', string='Related Transaction')
    property_id = fields.Many2one('villeside.property.listing', string='Related Property')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    expiry_date = fields.Datetime(string='Expiry Date')
    completed_date = fields.Datetime(string='Completed Date')
    sent_date = fields.Datetime(string='Sent Date')
    reminder_sent = fields.Boolean(default=False)
    notes = fields.Text(string='Internal Notes')

        # Authentisign integration
    authentisign_session_id = fields.Char(string='Authentisign Session ID', index=True)
    authentisign_status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('partially_signed', 'Partially Signed'),
        ('completed', 'All Signed'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ], string='Authentisign Status', tracking=True)
    authentisign_session_url = fields.Char(string='Authentisign Session URL')
    authentisign_last_event = fields.Char(string='Last Authentisign Event')
    authentisign_last_sync = fields.Datetime(string='Last Authentisign Sync')

    def action_send_for_signature(self):
        self.ensure_one()
        for signer in self.signer_ids:
            if not signer.access_token:
                signer.write({'access_token': str(uuid.uuid4())})
            # Send email with signing link
            template = self.env.ref('villeside_esign.email_template_esign_request', raise_if_not_found=False)
            if template:
                template.send_mail(signer.id, force_send=True)
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now(),
            'expiry_date': fields.Datetime.now() + timedelta(days=14),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _check_completion(self):
        self.ensure_one()
        all_signed = all(s.state == 'signed' for s in self.signer_ids)
        if all_signed and self.signer_ids:
            self.write({'state': 'completed', 'completed_date': fields.Datetime.now()})
        elif any(s.state == 'signed' for s in self.signer_ids):
            self.write({'state': 'partially_signed'})

    @api.model
    def _cron_check_expiry(self):
        expired = self.search([
            ('state', 'in', ['sent', 'partially_signed']),
            ('expiry_date', '<', fields.Datetime.now()),
        ])
        expired.write({'state': 'expired'})

    @api.model
    def _cron_send_reminders(self):
        pending = self.search([
            ('state', 'in', ['sent', 'partially_signed']),
            ('sent_date', '<', fields.Datetime.now() - timedelta(days=3)),
            ('reminder_sent', '=', False),
        ])
        for doc in pending:
            unsigned = doc.signer_ids.filtered(lambda s: s.state != 'signed')
            for signer in unsigned:
                template = self.env.ref('villeside_esign.email_template_esign_reminder', raise_if_not_found=False)
                if template:
                    template.send_mail(signer.id, force_send=True)
            doc.write({'reminder_sent': True})


class EsignSigner(models.Model):
    _name = 'villeside.esign.signer'
    _description = 'Document Signer'

    document_id = fields.Many2one('villeside.esign.document', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Signer', required=True)
    role = fields.Selection([
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
        ('agent', 'Agent'),
        ('broker', 'Broker'),
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
        ('witness', 'Witness'),
        ('notary', 'Notary'),
    ], string='Role', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('viewed', 'Viewed'),
        ('signed', 'Signed'),
        ('declined', 'Declined'),
    ], string='Status', default='pending')
    access_token = fields.Char(string='Access Token')
    signed_date = fields.Datetime(string='Signed Date')
    ip_address = fields.Char(string='IP Address')
    signature = fields.Binary(string='Signature')
    initials = fields.Binary(string='Initials')
    sequence = fields.Integer(default=10)

    def action_sign(self, signature_data, ip_address=None):
        self.ensure_one()
        self.write({
            'state': 'signed',
            'signed_date': fields.Datetime.now(),
            'signature': signature_data,
            'ip_address': ip_address or '',
        })
        self.document_id._check_completion()

    def action_decline(self, reason=None):
        self.ensure_one()
        self.write({'state': 'declined'})
        self.document_id.message_post(
            body='Signer %s declined: %s' % (self.partner_id.name, reason or 'No reason given')
        )


class EsignTemplate(models.Model):
    _name = 'villeside.esign.template'
    _description = 'E-Signature Template'

    name = fields.Char(string='Template Name', required=True)
    document_type = fields.Selection([
        ('purchase_agreement', 'Purchase Agreement'),
        ('listing_agreement', 'Listing Agreement'),
        ('lease', 'Lease Agreement'),
        ('addendum', 'Addendum'),
        ('disclosure', 'Disclosure'),
        ('other', 'Other'),
    ], string='Document Type')
    attachment_id = fields.Many2one('ir.attachment', string='Template File')
    field_ids = fields.One2many('villeside.esign.template.field', 'template_id', string='Fields')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)


class EsignTemplateField(models.Model):
    _name = 'villeside.esign.template.field'
    _description = 'Template Signature Field'

    template_id = fields.Many2one('villeside.esign.template', required=True, ondelete='cascade')
    field_type = fields.Selection([
        ('signature', 'Signature'),
        ('initials', 'Initials'),
        ('date', 'Date'),
        ('text', 'Text Input'),
        ('checkbox', 'Checkbox'),
        ('name', 'Full Name'),
    ], string='Field Type', required=True)
    signer_role = fields.Selection([
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
        ('agent', 'Agent'),
        ('broker', 'Broker'),
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
    ], string='Assigned Role')
    page = fields.Integer(string='Page Number', default=1)
    pos_x = fields.Float(string='X Position')
    pos_y = fields.Float(string='Y Position')
    width = fields.Float(string='Width', default=200)
    height = fields.Float(string='Height', default=50)
    required = fields.Boolean(default=True)