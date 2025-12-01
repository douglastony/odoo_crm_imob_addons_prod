from odoo import models, fields

STAGES_ORDER = [
    "Novo",
    "Primeiro Contato",
    "Qualificando",
    "Agendado",
    "Reagendar",
    "Preparando Pasta",
    "Pasta completa",
    "Análise",
    "Aprovado",
    "Reprovado",
    "Fluxo Agendado",
    "Aguardando Retorno",
    "Venda Fechada",
    "Repasse",
]

class CrmLead(models.Model):
    _inherit = "crm.lead"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        related="user_id.sales_unit_id",
        store=True,
        index=True
    )

    def write(self, vals):
        old_stages = {lead.id: lead.stage_id.name for lead in self}
        old_users = {lead.id: lead.user_id for lead in self}

        res = super(CrmLead, self).write(vals)

        # --- Lógica de mudança de corretor ---
        if "user_id" in vals:
            for lead in self:
                old_user = old_users[lead.id]
                new_user = lead.user_id
                if old_user and old_user != new_user:
                    # registrar histórico de "Reprovado" para o antigo corretor
                    lost_stage = self.env["crm.stage"].search([("name", "=", "Reprovado")], limit=1)
                    if lost_stage:
                        self.env["crm.lead.stage.history"].create({
                            "lead_id": lead.id,
                            "stage_id": lost_stage.id,
                            "user_id": old_user.id,
                            "date_stage_change": fields.Datetime.now(),
                            "lead_creation_date": lead.create_date,
                        })
                    # registrar histórico de "Novo" para o novo corretor
                    new_stage = self.env["crm.stage"].search([("name", "=", "Novo")], limit=1)
                    if new_stage:
                        self.env["crm.lead.stage.history"].create({
                            "lead_id": lead.id,
                            "stage_id": new_stage.id,
                            "user_id": new_user.id,
                            "date_stage_change": fields.Datetime.now(),
                            "lead_creation_date": lead.create_date,
                        })

        # --- Lógica de mudança de estágio ---
        if "stage_id" in vals:
            for lead in self:
                origin = old_stages[lead.id]
                dest = lead.stage_id.name

                def _create_history(stage_rec, user):
                    self.env["crm.lead.stage.history"].create({
                        "lead_id": lead.id,
                        "stage_id": stage_rec.id,
                        "user_id": user.id,
                        "date_stage_change": fields.Datetime.now(),
                        "lead_creation_date": lead.create_date,
                    })

                # Proteção contra estágios fora da lista
                if origin not in STAGES_ORDER or dest not in STAGES_ORDER:
                    _create_history(lead.stage_id, lead.user_id)
                    continue

                origin_index = STAGES_ORDER.index(origin)
                dest_index = STAGES_ORDER.index(dest)

                if dest_index > origin_index:
                    intermediarias = STAGES_ORDER[origin_index+1:dest_index]
                    for stage in intermediarias:
                        if stage not in ["Reprovado", "Reagendar"]:
                            stage_rec = self.env["crm.stage"].search([("name", "=", stage)], limit=1)
                            if stage_rec:
                                _create_history(stage_rec, lead.user_id)
                    _create_history(lead.stage_id, lead.user_id)

                elif dest in ["Reprovado", "Reagendar"]:
                    intermediarias = STAGES_ORDER[origin_index+1:dest_index]
                    for stage in intermediarias:
                        if stage not in ["Reprovado", "Reagendar"]:
                            stage_rec = self.env["crm.stage"].search([("name", "=", stage)], limit=1)
                            if stage_rec:
                                _create_history(stage_rec, lead.user_id)
                    _create_history(lead.stage_id, lead.user_id)

                else:
                    _create_history(lead.stage_id, lead.user_id)

        return res
