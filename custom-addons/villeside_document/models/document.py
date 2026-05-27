from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class DocumentFolder(models.Model):
    _name = 'villeside.document.folder'
    _description = 'Document Folder'
    _order = 'name'

    name = fields.Char(string='Folder Name', required=True)
    parent_id = fields.Many2one('villeside.document.folder', string='Parent Folder')
    child_ids = fields.One2many('villeside.document.folder', 'parent_id', string='Subfolders')
    document_ids = fields.One2many('villeside.document', 'folder_id', string='Documents')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    folder_type = fields.Selection([
        ('transaction', 'Transaction'),
        ('listing', 'Listing'),
        ('agent', 'Agent'),
        ('client', 'Client'),
        ('company', 'Company'),
        ('template', 'Templates'),
        ('compliance', 'Compliance'),
    ], string='Folder Type')
    access_group_ids = fields.Many2many('res.groups', string='Access Groups')


class Document(models.Model):
    _name = 'villeside.document'
    _description = 'Real Estate Document'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(string='Document Name', required=True)
    folder_id = fields.Many2one('villeside.document.folder', string='Folder')
    attachment_id = fields.Many2one('ir.attachment', string='File')
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(string='File Size')
    mimetype = fields.Char(string='MIME Type')
    document_type = fields.Selection([
        ('purchase_agreement', 'Purchase Agreement'),
        ('listing_agreement', 'Listing Agreement'),
        ('lease', 'Lease'),
        ('addendum', 'Addendum'),
        ('disclosure', 'Disclosure'),
        ('inspection', 'Inspection Report'),
        ('appraisal', 'Appraisal'),
        ('title', 'Title Report'),
        ('survey', 'Survey'),
        ('insurance', 'Insurance'),
        ('tax', 'Tax Document'),
        ('closing', 'Closing Statement'),
        ('commission', 'Commission Statement'),
        ('marketing', 'Marketing Material'),
        ('photo', 'Property Photo'),
        ('floorplan', 'Floor Plan'),
        ('license', 'Agent License'),
        ('compliance', 'Compliance Document'),
        ('other', 'Other'),
    ], string='Document Type')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('expired', 'Expired'),
    ], string='Status', default='active')
    property_id = fields.Many2one('villeside.property.listing', string='Property')
    transaction_id = fields.Many2one('villeside.transaction', string='Transaction')
    lead_id = fields.Many2one('crm.lead', string='Lead')
    partner_id = fields.Many2one('res.partner', string='Related Contact')
    agent_id = fields.Many2one('res.users', string='Agent')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    expiry_date = fields.Date(string='Expiry Date')
    version = fields.Integer(string='Version', default=1)
    previous_version_id = fields.Many2one('villeside.document', string='Previous Version')
    tag_ids = fields.Many2many('villeside.document.tag', string='Tags')
    notes = fields.Text(string='Notes')
    shared_with_portal = fields.Boolean(string='Shared with Portal', default=False)
    requires_signature = fields.Boolean(string='Requires Signature', default=False)
    signed = fields.Boolean(string='Signed', default=False)

    @api.model
    def _cron_check_expiry(self):
        expired = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', fields.Date.today()),
        ])
        expired.write({'state': 'expired'})


class DocumentTag(models.Model):
    _name = 'villeside.document.tag'
    _description = 'Document Tag'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color')


class DocumentChecklist(models.Model):
    _name = 'villeside.document.checklist'
    _description = 'Transaction Document Checklist'
    _order = 'sequence'

    name = fields.Char(string='Checklist Item', required=True)
    sequence = fields.Integer(default=10)
    checklist_type = fields.Selection([
        ('buyer', 'Buyer Transaction'),
        ('seller', 'Seller Transaction'),
        ('listing', 'New Listing'),
        ('rental', 'Rental'),
        ('commercial', 'Commercial'),
    ], string='Checklist Type', required=True)
    required = fields.Boolean(string='Required', default=True)
    document_type = fields.Selection([
        ('purchase_agreement', 'Purchase Agreement'),
        ('listing_agreement', 'Listing Agreement'),
        ('disclosure', 'Disclosure'),
        ('inspection', 'Inspection Report'),
        ('appraisal', 'Appraisal'),
        ('title', 'Title Report'),
        ('insurance', 'Insurance'),
        ('closing', 'Closing Statement'),
        ('other', 'Other'),
    ], string='Expected Document Type')
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)