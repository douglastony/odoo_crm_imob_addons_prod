from odoo import models, fields

STAGES_ORDER = [
    "Novo",
    "Primeiro Contato",
    "Qualificando",
    "Agendado",
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
        # pega estágio antigo antes de salvar
        old_stages = {lead.id: lead.stage_id.name for lead in self}
        res = super(CrmLead, self).write(vals)

        if "stage_id" in vals:
            for lead in self:
                origin = old_stages[lead.id]
                dest = lead.stage_id.name

                origin_index = STAGES_ORDER.index(origin)
                dest_index = STAGES_ORDER.index(dest)

                # indo para frente
                if dest_index > origin_index:
                    intermediarias = STAGES_ORDER[origin_index+1:dest_index]
                    for stage in intermediarias:
                        if stage not in ["Reprovado", "Reagendar"]:
                            self.env["crm.lead.stage.history"].create({
                                "lead_id": lead.id,
                                "stage_id": self.env["crm.stage"].search([("name","=",stage)], limit=1).id,
                                "user_id": lead.user_id.id,
                                "date_stage_change": fields.Datetime.now(),
                            })
                    # grava destino
                    self.env["crm.lead.stage.history"].create({
                        "lead_id": lead.id,
                        "stage_id": lead.stage_id.id,
                        "user_id": lead.user_id.id,
                        "date_stage_change": fields.Datetime.now(),
                    })

                # indo para Reprovado ou Reagendar
                elif dest in ["Reprovado", "Reagendar"]:
                    intermediarias = STAGES_ORDER[origin_index+1:dest_index]
                    for stage in intermediarias:
                        if stage not in ["Reprovado", "Reagendar"]:
                            self.env["crm.lead.stage.history"].create({
                                "lead_id": lead.id,
                                "stage_id": self.env["crm.stage"].search([("name","=",stage)], limit=1).id,
                                "user_id": lead.user_id.id,
                                "date_stage_change": fields.Datetime.now(),
                            })
                    # grava destino
                    self.env["crm.lead.stage.history"].create({
                        "lead_id": lead.id,
                        "stage_id": lead.stage_id.id,
                        "user_id": lead.user_id.id,
                        "date_stage_change": fields.Datetime.now(),
                    })

                # retrocesso → só destino
                else:
                    self.env["crm.lead.stage.history"].create({
                        "lead_id": lead.id,
                        "stage_id": lead.stage_id.id,
                        "user_id": lead.user_id.id,
                        "date_stage_change": fields.Datetime.now(),
                    })

        return res