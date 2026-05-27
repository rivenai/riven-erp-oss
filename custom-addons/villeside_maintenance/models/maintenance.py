from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    _name = 'villeside.maintenance.request'
    _description = 'Property Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, create_date desc'

    name = fields.Char(string='Request Title', required=True, tracking=True)
    sequence = fields.Char(string='Reference', readonly=True, copy=False)
    state = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', tracking=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Emergency'),
    ], string='Priority', default='1')
    category = fields.Selection([
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('hvac', 'HVAC'),
        ('appliance', 'Appliance'),
        ('structural', 'Structural'),
        ('pest', 'Pest Control'),
        ('landscaping', 'Landscaping'),
        ('painting', 'Painting'),
        ('flooring', 'Flooring'),
        ('roofing', 'Roofing'),
        ('general', 'General'),
        ('safety', 'Safety/Security'),
        ('cleaning', 'Cleaning'),
    ], string='Category', required=True)
    description = fields.Text(string='Description')
    property_id = fields.Many2one('villeside.property.listing', string='Property')
    unit_number = fields.Char(string='Unit Number')
    tenant_id = fields.Many2one('res.partner', string='Tenant')
    owner_id = fields.Many2one('res.partner', string='Property Owner')
    vendor_id = fields.Many2one('res.partner', string='Assigned Vendor')
    assigned_user_id = fields.Many2one('res.users', string='Assigned To')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    scheduled_date = fields.Datetime(string='Scheduled Date')
    completed_date = fields.Datetime(string='Completed Date')
    estimated_cost = fields.Monetary(string='Estimated Cost', currency_field='currency_id')
    actual_cost = fields.Monetary(string='Actual Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    attachment_ids = fields.Many2many('ir.attachment', string='Photos/Documents')
    notes = fields.Text(string='Internal Notes')
    tenant_accessible = fields.Boolean(string='Visible to Tenant', default=True)
    recurring = fields.Boolean(string='Recurring', default=False)
    recurrence_interval = fields.Integer(string='Recurrence Interval (Days)')
    next_recurrence = fields.Date(string='Next Recurrence')
    work_order_ids = fields.One2many('villeside.maintenance.workorder', 'request_id', string='Work Orders')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence'):
                vals['sequence'] = self.env['ir.sequence'].next_by_code('villeside.maintenance.request') or 'MR/NEW'
        return super().create(vals_list)

    def action_assign(self):
        self.write({'state': 'assigned'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed', 'completed_date': fields.Datetime.now()})
        if self.recurring and self.recurrence_interval:
            self.write({'next_recurrence': fields.Date.today() + timedelta(days=self.recurrence_interval)})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def _cron_create_recurring(self):
        due = self.search([
            ('recurring', '=', True),
            ('next_recurrence', '<=', fields.Date.today()),
            ('state', '=', 'completed'),
        ])
        for req in due:
            new_req = req.copy({
                'state': 'new',
                'sequence': False,
                'completed_date': False,
                'actual_cost': 0,
                'scheduled_date': False,
            })
            req.write({
                'next_recurrence': fields.Date.today() + timedelta(days=req.recurrence_interval)
            })


class MaintenanceWorkOrder(models.Model):
    _name = 'villeside.maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread']

    request_id = fields.Many2one('villeside.maintenance.request', required=True, ondelete='cascade')
    name = fields.Char(string='Work Order', required=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent to Vendor'),
        ('accepted', 'Accepted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('invoiced', 'Invoiced'),
    ], string='Status', default='draft', tracking=True)
    scheduled_date = fields.Datetime(string='Scheduled Date')
    completed_date = fields.Datetime(string='Completed Date')
    estimated_hours = fields.Float(string='Estimated Hours')
    actual_hours = fields.Float(string='Actual Hours')
    labor_cost = fields.Monetary(string='Labor Cost', currency_field='currency_id')
    material_cost = fields.Monetary(string='Material Cost', currency_field='currency_id')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='request_id.currency_id')
    notes = fields.Text(string='Work Notes')
    invoice_id = fields.Many2one('account.move', string='Invoice')

    @api.depends('labor_cost', 'material_cost')
    def _compute_total(self):
        for rec in self:
            rec.total_cost = rec.labor_cost + rec.material_cost