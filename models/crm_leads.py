from odoo import models, fields, api
from datetime import timedelta

class CrmLead(models.Model):
    _inherit = "crm.lead"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        related="user_id.sales_unit_id",
        store=True,
        index=True
    )

    modification_period = fields.Selection([
        ('today', 'Hoje'),
        ('yesterday', 'Ontem'),
        ('this_week', 'Esta Semana'),
        ('last_week', 'Semana Passada'),
        ('this_month', 'Mês Atual'),
        ('last_month', 'Mês Passado'),
        ('this_year', 'Ano Atual'),
    ], string="Período de Modificação", compute="_compute_modification_period", store=True)

    @api.depends('date_last_stage_update')
    def _compute_modification_period(self):
        today = fields.Date.today()
        for lead in self:
            date = lead.date_last_stage_update.date() if lead.date_last_stage_update else None
            if not date:
                lead.modification_period = False
                continue

            if date == today:
                lead.modification_period = 'today'
            elif date == today - timedelta(days=1):
                lead.modification_period = 'yesterday'
            elif date >= today - timedelta(days=today.weekday()):
                lead.modification_period = 'this_week'
            elif date >= today - timedelta(days=today.weekday()+7) and date < today - timedelta(days=today.weekday()):
                lead.modification_period = 'last_week'
            elif date.month == today.month and date.year == today.year:
                lead.modification_period = 'this_month'
            elif (date.month == (today.month - 1 if today.month > 1 else 12)) and \
                 (date.year == today.year if today.month > 1 else today.year - 1):
                lead.modification_period = 'last_month'
            elif date.year == today.year:
                lead.modification_period = 'this_year'
            else:
                lead.modification_period = False