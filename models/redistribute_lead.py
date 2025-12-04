from odoo import models, fields, api

class RedistributeLeadWizard(models.TransientModel):
    _name = 'redistribute.lead.wizard'
    _description = 'Redistribuição de Leads'

    source_user_id = fields.Many2one(
        'res.users',
        string='Corretor Inativo',
        required=True,
        domain=lambda self: [
        ('active', '=', False),
        ('id', 'in', self.env.user.allowed_user_ids.ids)
        ]
    )
    target_user_ids = fields.Many2many(
        'res.users',
        string='Corretores Ativos',
        required=True,
        domain=lambda self: [('id', 'in', self.env.user.allowed_user_ids.ids)]
    )

    def action_redistribute(self):
        # Buscar todos os leads do corretor inativo
        leads = self.env['crm.lead'].search([('user_id', '=', self.source_user_id.id)])

        # Buscar estágio "Novo"
        stage_novo = self.env['crm.stage'].search([('name', '=', 'Novo')], limit=1)

        # Filtrar leads que NÃO estão em "Venda Fechada" ou "Repasse"
        leads = leads.filtered(
            lambda l: l.stage_id.name not in ["Venda Fechada", "Repasse"]
        )

        # Distribuir round-robin entre os corretores escolhidos
        target_users = self.target_user_ids
        i = 0
        for lead in leads:
            new_user = target_users[i % len(target_users)]
            lead.write({
                'user_id': new_user.id,
                'stage_id': stage_novo.id if stage_novo else lead.stage_id.id,
                # opcional: resetar prioridade para aparecer no topo
                'priority': '3',  # Alta prioridade
                'date_open': fields.Datetime.now(),
            })
            i += 1
