from odoo import models, fields, api

class RedistributeLeadWizard(models.TransientModel):
    _name = 'redistribute.lead.wizard'
    _description = 'Redistribuição de Leads'

    source_user_id = fields.Many2one(
        'res.users',
        string='Corretor Origem',
        required=True,
        domain=lambda self: [
            ('id', 'in', self.env.user.allowed_user_ids.ids)
        ],
        context={'active_test': False}  # 🔑 inclui ativos e inativos
    )

    target_user_ids = fields.Many2many(
        'res.users',
        string='Corretores Destino',
        required=True,
        domain=lambda self: [('id', 'in', self.env.user.allowed_user_ids.ids)]
    )

    def action_redistribute(self):
        # 🔎 Agora não bloqueia se o corretor estiver ativo
        leads = self.env['crm.lead'].search([('user_id', '=', self.source_user_id.id)])
        stage_novo = self.env['crm.stage'].search([('name', '=', 'Novo')], limit=1)

        leads = leads.filtered(lambda l: l.stage_id.name not in ["Venda Fechada", "Repasse"])

        target_users = self.target_user_ids
        i = 0
        moved = []
        for lead in leads:
            old_user = lead.user_id
            old_stage = lead.stage_id
            new_user = target_users[i % len(target_users)]
            new_stage = stage_novo or lead.stage_id

            lead.write({
                'user_id': new_user.id,
                'stage_id': new_stage.id,
                'priority': '3',
                'date_open': fields.Datetime.now(),
            })
            moved.append(f"{lead.name} → {new_user.name}")
            i += 1

            # Grava log com user e stage antigos/novos
            self.env['crm.lead.redistribution.log'].create({
                'lead_id': lead.id,
                'old_user_id': old_user.id,
                'new_user_id': new_user.id,
                'old_stage_id': old_stage.id,
                'new_stage_id': new_stage.id,
                'done_date': fields.Datetime.now(),
                'executor_id': self.env.user.id,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Redistribuição concluída',
                'message': "Leads redistribuídos:\n" + "\n".join(moved),
                'sticky': False,
            }
        }
