from odoo import models, fields, api
from datetime import datetime

class LeadStageHistory(models.Model):
    _name = "crm.lead.stage.history"
    _description = "Histórico de Movimentação de Etapas do Lead"

    lead_id = fields.Many2one("crm.lead", string="Lead", required=True, ondelete="cascade")
    stage_id = fields.Many2one("crm.stage", string="Etapa", required=True)
    user_id = fields.Many2one("res.users", string="Responsável", required=True)
    date_stage_change = fields.Datetime(string="Data da Mudança", default=fields.Datetime.now, required=True)
