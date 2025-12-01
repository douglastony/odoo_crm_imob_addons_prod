from odoo import models, fields

class LeadStageHistory(models.Model):
    _name = "crm.lead.stage.history"
    _description = "Histórico de Movimentação de Etapas do Lead"
    _rec_name = "lead_id"  # facilita identificação no backend

    lead_id = fields.Many2one(
        "crm.lead",
        string="Lead",
        required=True,
        ondelete="restrict",   # mantém histórico mesmo se lead for apagado
        index=True
    )
    stage_id = fields.Many2one(
        "crm.stage",
        string="Etapa",
        required=True,
        index=True
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsável",
        required=True,
        index=True
    )
    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        string="Unidade de Vendas",
        related="user_id.sales_unit_id",
        store=True,
        index=True
    )
    date_stage_change = fields.Datetime(
        string="Data da Mudança",
        default=fields.Datetime.now,
        required=True
    )
    lead_creation_date = fields.Datetime(
        string="Data de Criação do Lead",
        required=True
    )
    source_id = fields.Many2one(
        "utm.source",
        string="Origem do Lead",
        related="lead_id.source_id",
        store=True,
        index=True
    )
    campaign_id = fields.Many2one(
        "utm.campaign",
        string="Campanha",
        related="lead_id.campaign_id",
        store=True,
        index=True
    )
    medium_id = fields.Many2one(
        "utm.medium",
        string="Mídia",
        related="lead_id.medium_id",
        store=True,
        index=True
    )


    # Sobrescrevemos create para congelar os dados no momento da gravação
    def create(self, vals):
        if vals.get("user_id"):
            user = self.env["res.users"].browse(vals["user_id"])
            vals["sales_unit_id"] = user.sales_unit_id.id if user.sales_unit_id else False

        if vals.get("lead_id"):
            lead = self.env["crm.lead"].browse(vals["lead_id"])
            vals["lead_creation_date"] = lead.create_date
        return super(LeadStageHistory, self).create(vals)
