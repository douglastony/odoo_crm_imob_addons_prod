from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Expediente
    default_hora_inicio = fields.Float(
        string="Hora de início do expediente",
        config_parameter="crm_sales_unit.default_hora_inicio",
        default=13.1667  # 13h10
    )
    default_hora_fim = fields.Float(
        string="Hora de fim do expediente",
        config_parameter="crm_sales_unit.default_hora_fim",
        default=20.0
    )

    # Cooldown
    default_lead_cooldown = fields.Integer(
        string="Tempo mínimo entre leads (minutos)",
        config_parameter="crm_sales_unit.default_lead_cooldown",
        default=5
    )

    # SLA de atuação no lead
    default_lead_sla = fields.Integer(
        string="Prazo para corretor atuar (minutos)",
        config_parameter="crm_sales_unit.default_lead_sla",
        default=15
    )
