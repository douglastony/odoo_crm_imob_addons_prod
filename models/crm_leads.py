from odoo import models, fields, api
from datetime import datetime, timedelta


class CrmLead(models.Model):
    _inherit = "crm.lead"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        related="user_id.sales_unit_id",
        store=True,
        index=True
    )

    def distribute_unassigned_leads(self):
        """Distribui leads do bolsão → apenas da 1ª coluna, respeitando cooldown"""
        stage_new = self.env["crm.stage"].search([], order="sequence asc", limit=1)
        if not stage_new:
            return

        unassigned = self.search([
            ("user_id", "=", False),
            ("stage_id", "=", stage_new.id),
        ])

        if not unassigned:
            return

        cooldown_minutes = int(self.env["ir.config_parameter"].sudo().get_param(
            "crm_sales_unit.cooldown_minutes", 5
        ))
        now = fields.Datetime.now()

        # pegar fila de corretores ativos
        corretores = self.env["res.users"].search([("is_checked_in", "=", True)])

        if not corretores:
            return  # ninguém na fila

        idx = 0
        for lead in unassigned:
            attempts = 0
            while attempts < len(corretores):
                corretor = corretores[idx % len(corretores)]
                idx += 1
                attempts += 1

                # checar cooldown
                if corretor.last_lead_assigned_at:
                    diff = now - corretor.last_lead_assigned_at
                    if diff < timedelta(minutes=cooldown_minutes):
                        continue  # pula esse corretor

                # atribui lead
                lead.user_id = corretor
                corretor.last_lead_assigned_at = now
                break
