from odoo import models, fields, api


class RealEstateTransaction(models.Model):
    _name = 'villeside.transaction'
    _description = 'Real Estate Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Transaction #', required=True, copy=False, default='New')
    property_id = fields.Many2one('villeside.property', string='Property')
    property_address = fields.Char(string='Property Address', related='property_id.street', store=True)
    lead_id = fields.Many2one('crm.lead', string='CRM Opportunity')

    # Transaction type
    transaction_type = fields.Selection([
        ('purchase', 'Purchase'),
        ('sale', 'Sale/Listing'),
        ('lease', 'Lease'),
        ('dual', 'Dual Agency'),
    ], string='Type', required=True, tracking=True)

    # Status workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('offer', 'Offer Submitted'),
        ('counter', 'Counter Offer'),
        ('accepted', 'Offer Accepted'),
        ('under_contract', 'Under Contract'),
        ('inspection', 'Inspection Period'),
        ('appraisal', 'Appraisal'),
        ('title', 'Title Review'),
        ('financing', 'Financing Contingency'),
        ('clear_to_close', 'Clear to Close'),
        ('closing', 'At Closing Table'),
        ('closed', 'Closed'),
        ('fell_through', 'Fell Through'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)

    # Parties
    buyer_id = fields.Many2one('res.partner', string='Buyer')
    seller_id = fields.Many2one('res.partner', string='Seller')
    listing_agent_id = fields.Many2one('hr.employee', string='Listing Agent')
    buyer_agent_id = fields.Many2one('hr.employee', string='Buyer Agent')
    transaction_coordinator_id = fields.Many2one('hr.employee', string='Transaction Coordinator')
    title_company_id = fields.Many2one('res.partner', string='Title Company')
    lender_id = fields.Many2one('res.partner', string='Lender')
    inspector_id = fields.Many2one('res.partner', string='Inspector')
    appraiser_id = fields.Many2one('res.partner', string='Appraiser')
    attorney_id = fields.Many2one('res.partner', string='Attorney')

    # Financial
    offer_price = fields.Monetary(string='Offer Price', currency_field='currency_id', tracking=True)
    accepted_price = fields.Monetary(string='Accepted Price', currency_field='currency_id')
    sale_price = fields.Monetary(string='Final Sale Price', currency_field='currency_id')
    earnest_money = fields.Monetary(string='Earnest Money', currency_field='currency_id')
    seller_concessions = fields.Monetary(string='Seller Concessions', currency_field='currency_id')
    buyer_closing_costs = fields.Monetary(string='Buyer Closing Costs (Est)', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Key dates
    offer_date = fields.Date(string='Offer Date', tracking=True)
    acceptance_date = fields.Date(string='Acceptance Date')
    inspection_deadline = fields.Date(string='Inspection Deadline')
    inspection_complete_date = fields.Date(string='Inspection Complete')
    appraisal_ordered_date = fields.Date(string='Appraisal Ordered')
    appraisal_complete_date = fields.Date(string='Appraisal Complete')
    appraisal_value = fields.Monetary(string='Appraised Value', currency_field='currency_id')
    financing_deadline = fields.Date(string='Financing Contingency Deadline')
    financing_approved_date = fields.Date(string='Financing Approved')
    title_received_date = fields.Date(string='Title Commitment Received')
    clear_to_close_date = fields.Date(string='Clear to Close Date')
    closing_date = fields.Date(string='Closing Date', tracking=True)
    actual_closing_date = fields.Date(string='Actual Closing Date')
    possession_date = fields.Date(string='Possession Date')

    # Commission
    listing_commission_pct = fields.Float(string='Listing Commission %', default=3.0)
    buyer_commission_pct = fields.Float(string='Buyer Commission %', default=3.0)
    listing_commission_amount = fields.Monetary(compute='_compute_commissions', string='Listing Commission $', currency_field='currency_id')
    buyer_commission_amount = fields.Monetary(compute='_compute_commissions', string='Buyer Commission $', currency_field='currency_id')
    commission_line_id = fields.Many2one('villeside.commission.line', string='Commission Record')

    # Compliance checklist
    checklist_ids = fields.One2many('villeside.transaction.checklist', 'transaction_id', string='Compliance Checklist')

    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents')

    # Notes
    notes = fields.Html(string='Internal Notes')
    special_terms = fields.Text(string='Special Terms/Conditions')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('villeside.transaction') or 'New'
        return super().create(vals_list)

    @api.depends('sale_price', 'accepted_price', 'listing_commission_pct', 'buyer_commission_pct')
    def _compute_commissions(self):
        for rec in self:
            price = rec.sale_price or rec.accepted_price or 0
            rec.listing_commission_amount = price * (rec.listing_commission_pct / 100.0)
            rec.buyer_commission_amount = price * (rec.buyer_commission_pct / 100.0)


class TransactionChecklist(models.Model):
    _name = 'villeside.transaction.checklist'
    _description = 'Transaction Compliance Checklist Item'
    _order = 'sequence, name'

    transaction_id = fields.Many2one('villeside.transaction', ondelete='cascade')
    name = fields.Char(string='Item', required=True)
    sequence = fields.Integer(default=10)
    is_required = fields.Boolean(string='Required', default=True)
    is_complete = fields.Boolean(string='Complete')
    completed_date = fields.Date(string='Completed Date')
    completed_by = fields.Many2one('res.users', string='Completed By')
    due_date = fields.Date(string='Due Date')
    document_id = fields.Many2one('ir.attachment', string='Document')
    category = fields.Selection([
        ('contract', 'Contract Documents'),
        ('disclosure', 'Disclosures'),
        ('inspection', 'Inspections'),
        ('financing', 'Financing'),
        ('title', 'Title & Closing'),
        ('compliance', 'Compliance'),
    ], string='Category')
    notes = fields.Text(string='Notes')