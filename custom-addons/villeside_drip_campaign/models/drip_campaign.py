from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class DripCampaign(models.Model):
    _name = 'villeside.drip.campaign'
    _description = 'Drip Email Campaign'
    _order = 'sequence'

    name = fields.Char(string='Campaign Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    campaign_type = fields.Selection([
        ('new_lead', 'New Lead Nurture'),
        ('buyer_nurture', 'Buyer Nurture'),
        ('seller_nurture', 'Seller Nurture'),
        ('past_client', 'Past Client Follow-up'),
        ('open_house', 'Open House Follow-up'),
        ('anniversary', 'Home Anniversary'),
        ('birthday', 'Birthday Campaign'),
        ('investor', 'Investor Updates'),
        ('relocation', 'Relocation Guide'),
        ('fsbo', 'FSBO Outreach'),
        ('expired', 'Expired Listing'),
    ], string='Campaign Type', required=True)
    description = fields.Text(string='Description')
    step_ids = fields.One2many('villeside.drip.step', 'campaign_id', string='Steps')
    lead_ids = fields.Many2many('crm.lead', string='Enrolled Leads')
    enrollment_count = fields.Integer(compute='_compute_counts', string='Enrolled')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    tag_ids = fields.Many2many('crm.tag', string='Auto-Enroll Tags')
    auto_enroll = fields.Boolean(string='Auto-Enroll New Leads', default=False)
    auto_enroll_stage_id = fields.Many2one('crm.stage', string='Enroll at Stage')
    stop_on_reply = fields.Boolean(string='Stop on Reply', default=True)
    stop_on_conversion = fields.Boolean(string='Stop on Conversion', default=True)

    @api.depends('lead_ids')
    def _compute_counts(self):
        for rec in self:
            rec.enrollment_count = len(rec.lead_ids)

    def action_enroll_lead(self, lead):
        self.ensure_one()
        if lead not in self.lead_ids:
            self.write({'lead_ids': [(4, lead.id)]})
            first_step = self.step_ids.sorted('sequence')[:1]
            if first_step:
                self.env['villeside.drip.queue'].create({
                    'campaign_id': self.id,
                    'step_id': first_step.id,
                    'lead_id': lead.id,
                    'scheduled_date': fields.Datetime.now() + timedelta(hours=first_step.delay_hours),
                })

    @api.model
    def _cron_process_drip_queue(self):
        queue = self.env['villeside.drip.queue'].search([
            ('state', '=', 'pending'),
            ('scheduled_date', '<=', fields.Datetime.now()),
        ])
        for item in queue:
            try:
                item.action_send()
            except Exception as e:
                _logger.error('Drip send failed for queue %s: %s', item.id, e)
                item.write({'state': 'failed'})


class DripStep(models.Model):
    _name = 'villeside.drip.step'
    _description = 'Drip Campaign Step'
    _order = 'sequence'

    campaign_id = fields.Many2one('villeside.drip.campaign', required=True, ondelete='cascade')
    name = fields.Char(string='Step Name', required=True)
    sequence = fields.Integer(default=10)
    delay_hours = fields.Integer(string='Delay (Hours)', default=24)
    step_type = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('task', 'Create Task'),
        ('activity', 'Schedule Activity'),
    ], string='Action Type', default='email', required=True)
    mail_template_id = fields.Many2one('mail.template', string='Email Template')
    sms_template = fields.Text(string='SMS Template')
    subject = fields.Char(string='Subject Line')
    body_html = fields.Html(string='Email Body')
    condition = fields.Selection([
        ('always', 'Always Send'),
        ('no_reply', 'Only if No Reply'),
        ('no_open', 'Only if Not Opened'),
        ('clicked', 'Only if Link Clicked'),
    ], string='Condition', default='always')


class DripQueue(models.Model):
    _name = 'villeside.drip.queue'
    _description = 'Drip Queue Item'
    _order = 'scheduled_date'

    campaign_id = fields.Many2one('villeside.drip.campaign', required=True)
    step_id = fields.Many2one('villeside.drip.step', required=True)
    lead_id = fields.Many2one('crm.lead', required=True)
    scheduled_date = fields.Datetime(string='Scheduled Date')
    sent_date = fields.Datetime(string='Sent Date')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('skipped', 'Skipped'),
        ('failed', 'Failed'),
    ], string='Status', default='pending')
    opened = fields.Boolean(default=False)
    clicked = fields.Boolean(default=False)
    replied = fields.Boolean(default=False)

    def action_send(self):
        self.ensure_one()
        step = self.step_id
        if step.condition == 'no_reply' and self._check_replied():
            self.write({'state': 'skipped'})
            return
        if step.step_type == 'email' and step.mail_template_id:
            step.mail_template_id.send_mail(self.lead_id.id, force_send=True)
        elif step.step_type == 'task':
            self.env['project.task'].create({
                'name': step.name,
                'description': 'Auto-created by drip campaign: %s' % self.campaign_id.name,
                'user_ids': [(4, self.lead_id.user_id.id)] if self.lead_id.user_id else [],
            })
        self.write({'state': 'sent', 'sent_date': fields.Datetime.now()})
        # Schedule next step
        next_steps = self.campaign_id.step_ids.filtered(
            lambda s: s.sequence > step.sequence
        ).sorted('sequence')[:1]
        if next_steps:
            self.env['villeside.drip.queue'].create({
                'campaign_id': self.campaign_id.id,
                'step_id': next_steps.id,
                'lead_id': self.lead_id.id,
                'scheduled_date': fields.Datetime.now() + timedelta(hours=next_steps.delay_hours),
            })

    def _check_replied(self):
        messages = self.env['mail.message'].search([
            ('res_id', '=', self.lead_id.id),
            ('model', '=', 'crm.lead'),
            ('message_type', '=', 'comment'),
            ('author_id', '=', self.lead_id.partner_id.id),
        ], limit=1)
        return bool(messages)