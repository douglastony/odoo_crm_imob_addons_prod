from odoo import models, fields
from odoo.exceptions import UserError

class LeadRedistributionLog(models.Model):
    _name = 'crm.lead.redistribution.log'
    _description = 'Log de Redistribuição de Leads'
    _order = 'create_date desc'

    lead_id = fields.Many2one('crm.lead', string='Lead', required=True, ondelete='cascade')
    old_user_id = fields.Many2one('res.users', string='Corretor Original', required=True)
    new_user_id = fields.Many2one('res.users', string='Corretor Novo', required=True)
    old_stage_id = fields.Many2one('crm.stage', string='Estágio Original', required=True)
    new_stage_id = fields.Many2one('crm.stage', string='Estágio Novo', required=True)
    done_date = fields.Datetime(string='Data da Ação', default=lambda self: fields.Datetime.now())
    executor_id = fields.Many2one('res.users', string='Executor', required=True, default=lambda self: self.env.user)
    undone = fields.Boolean(string='Desfeito', default=False)

    def action_undo(self):
        moved_back = []
        for log in self.filtered(lambda l: not l.undone):
            if log.new_user_id.id not in self.env.user.allowed_user_ids.ids:
                raise UserError(
                    f"Não é possível desfazer: o corretor {log.new_user_id.name} não está mais sob sua hierarquia."
                )

            # Atualiza o lead para voltar ao corretor e estágio originais
            log.lead_id.sudo().write({
                'user_id': log.old_user_id.id,
                'stage_id': log.old_stage_id.id,
                'priority': '3',
                'date_open': fields.Datetime.now(),
            })

            # Cria um novo log representando o undo
            self.env['crm.lead.redistribution.log'].sudo().create({
                'lead_id': log.lead_id.id,
                'old_user_id': log.new_user_id.id,   # quem estava com o lead
                'new_user_id': log.old_user_id.id,   # voltando para o antigo
                'old_stage_id': log.new_stage_id.id,
                'new_stage_id': log.old_stage_id.id,
                'executor_id': self.env.user.id,
                'done_date': fields.Datetime.now(),  # momento da desfeita
            })

            # Marca o log original como desfeito
            log.undone = True
            moved_back.append(f"{log.lead_id.name} → {log.old_user_id.name}")

        if moved_back:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Undo concluído',
                    'message': "Leads devolvidos:\n" + "\n".join(moved_back),
                    'sticky': False,
                }
            }
