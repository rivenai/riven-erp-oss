from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class TenantLease(models.Model):
    _name = 'villeside.tenant.lease'
    _description = 'Tenant Lease Agreement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Lease Reference', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('terminated', 'Terminated'),
    ], string='Status', default='draft', tracking=True)
    tenant_id = fields.Many2one('res.partner', string='Tenant', required=True)
    co_tenant_ids = fields.Many2many('res.partner', string='Co-Tenants')
    property_id = fields.Many2one('villeside.property.listing', string='Property')
    unit_number = fields.Char(string='Unit Number')
    owner_id = fields.Many2one('res.partner', string='Property Owner')
    manager_id = fields.Many2one('res.users', string='Property Manager')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    start_date = fields.Date(string='Lease Start', required=True)
    end_date = fields.Date(string='Lease End', required=True)
    monthly_rent = fields.Monetary(string='Monthly Rent', currency_field='currency_id')
    security_deposit = fields.Monetary(string='Security Deposit', currency_field='currency_id')
    pet_deposit = fields.Monetary(string='Pet Deposit', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    rent_due_day = fields.Integer(string='Rent Due Day', default=1)
    late_fee = fields.Monetary(string='Late Fee', currency_field='currency_id')
    grace_period_days = fields.Integer(string='Grace Period (Days)', default=5)
    lease_type = fields.Selection([
        ('fixed', 'Fixed Term'),
        ('month_to_month', 'Month-to-Month'),
        ('sublease', 'Sublease'),
    ], string='Lease Type', default='fixed')
    auto_renew = fields.Boolean(string='Auto-Renew', default=False)
    renewal_term_months = fields.Integer(string='Renewal Term (Months)', default=12)
    notice_period_days = fields.Integer(string='Notice Period (Days)', default=60)
    payment_ids = fields.One2many('villeside.tenant.payment', 'lease_id', string='Payments')
    document_ids = fields.Many2many('ir.attachment', string='Lease Documents')
    notes = fields.Text(string='Notes')
    pets_allowed = fields.Boolean(string='Pets Allowed', default=False)
    parking_included = fields.Boolean(string='Parking Included', default=False)
    utilities_included = fields.Char(string='Utilities Included')
    move_in_date = fields.Date(string='Move-In Date')
    move_out_date = fields.Date(string='Move-Out Date')
    move_in_inspection = fields.Text(string='Move-In Inspection Notes')
    move_out_inspection = fields.Text(string='Move-Out Inspection Notes')

    def action_activate(self):
        self.write({'state': 'active'})

    def action_terminate(self):
        self.write({'state': 'terminated'})

    def action_renew(self):
        self.ensure_one()
        new_start = self.end_date + timedelta(days=1)
        new_end = new_start + timedelta(days=self.renewal_term_months * 30)
        self.write({
            'state': 'renewed',
        })
        return self.copy({
            'start_date': new_start,
            'end_date': new_end,
            'state': 'active',
        })

    @api.model
    def _cron_check_expiring(self):
        threshold = fields.Date.today() + timedelta(days=60)
        expiring = self.search([
            ('state', '=', 'active'),
            ('end_date', '<=', threshold),
            ('end_date', '>=', fields.Date.today()),
        ])
        expiring.write({'state': 'expiring'})
        expired = self.search([
            ('state', 'in', ['active', 'expiring']),
            ('end_date', '<', fields.Date.today()),
        ])
        for lease in expired:
            if lease.auto_renew:
                lease.action_renew()
            else:
                lease.write({'state': 'expired'})


class TenantPayment(models.Model):
    _name = 'villeside.tenant.payment'
    _description = 'Tenant Rent Payment'
    _order = 'payment_date desc'

    lease_id = fields.Many2one('villeside.tenant.lease', required=True, ondelete='cascade')
    tenant_id = fields.Many2one('res.partner', related='lease_id.tenant_id', store=True)
    payment_date = fields.Date(string='Payment Date')
    due_date = fields.Date(string='Due Date')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    late_fee_amount = fields.Monetary(string='Late Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='lease_id.currency_id')
    payment_method = fields.Selection([
        ('check', 'Check'),
        ('ach', 'ACH/Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('cash', 'Cash'),
        ('money_order', 'Money Order'),
        ('online', 'Online Portal'),
    ], string='Payment Method')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('late', 'Late'),
        ('partial', 'Partial'),
        ('bounced', 'Bounced/NSF'),
    ], string='Status', default='pending')
    reference = fields.Char(string='Reference Number')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    notes = fields.Text(string='Notes')


class TenantScreening(models.Model):
    _name = 'villeside.tenant.screening'
    _description = 'Tenant Screening Application'
    _inherit = ['mail.thread']

    name = fields.Char(string='Application Reference', required=True)
    applicant_id = fields.Many2one('res.partner', string='Applicant', required=True)
    property_id = fields.Many2one('villeside.property.listing', string='Property')
    state = fields.Selection([
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('waitlisted', 'Waitlisted'),
    ], string='Status', default='submitted', tracking=True)
    application_date = fields.Date(string='Application Date', default=fields.Date.today)
    desired_move_in = fields.Date(string='Desired Move-In')
    monthly_income = fields.Monetary(string='Monthly Income', currency_field='currency_id')
    employer = fields.Char(string='Employer')
    employment_length = fields.Char(string='Length of Employment')
    previous_address = fields.Text(string='Previous Address')
    previous_landlord = fields.Char(string='Previous Landlord')
    previous_landlord_phone = fields.Char(string='Previous Landlord Phone')
    credit_score = fields.Integer(string='Credit Score')
    background_check = fields.Boolean(string='Background Check Passed')
    eviction_history = fields.Boolean(string='Prior Evictions', default=False)
    pets = fields.Boolean(string='Has Pets', default=False)
    pet_details = fields.Text(string='Pet Details')
    vehicles = fields.Integer(string='Number of Vehicles')
    occupants = fields.Integer(string='Number of Occupants')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Screening Notes')
    application_fee_paid = fields.Boolean(string='Application Fee Paid', default=False)