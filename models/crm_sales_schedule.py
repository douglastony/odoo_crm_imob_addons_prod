from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CrmSalesSchedule(models.Model):
    _name = "crm.sales.schedule"
    _description = "Configuração de Expediente de Vendas"
    _order = "date desc"

    date = fields.Date(
        string="Data",
        required=True,
        default=fields.Date.context_today,
        help="Data específica do expediente (sobrescreve padrão)."
    )
    hora_inicio = fields.Float(
        string="Hora Início",
        required=True,
        default=13.1667,  # 13h10
        help="Formato decimal: 13.5 = 13h30"
    )
    hora_fim = fields.Float(
        string="Hora Fim",
        required=True,
        default=20.0,
        help="Formato decimal: 20.0 = 20h00"
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("unique_date", "unique(date)", "Já existe configuração para esta data!")
    ]

    @api.constrains("hora_inicio", "hora_fim")
    def _check_hours(self):
        for rec in self:
            if rec.hora_inicio >= rec.hora_fim:
                raise ValidationError("Hora de início deve ser menor que hora de fim.")

    # --- Método central ---
    @api.model
    def is_in_working_hours(self):
        """Retorna True se agora está dentro do expediente"""
        now = fields.Datetime.now()
        today = fields.Date.today()

        # 1) Configuração específica do dia
        sched = self.search([("date", "=", today), ("active", "=", True)], limit=1)

        if sched:
            start, end = sched.hora_inicio, sched.hora_fim
        else:
            # 2) Horário padrão em parâmetros globais
            start = float(self.env["ir.config_parameter"].sudo().get_param(
                "crm_sales_unit.default_hora_inicio", 13.1667))
            end = float(self.env["ir.config_parameter"].sudo().get_param(
                "crm_sales_unit.default_hora_fim", 20.0))

        current = now.hour + now.minute / 60.0
        return start <= current <= end
