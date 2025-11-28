from odoo import http
from odoo.http import request

class FunnelController(http.Controller):

    @http.route('/crm_funnel_dashboard/users', type='json', auth='user')
    def users(self):
        """Retorna lista de usuários (corretores) para filtro"""
        users = request.env['res.users'].sudo().search([])
        return [{'id': u.id, 'name': u.name} for u in users]

    @http.route('/crm_funnel_dashboard/data', type='json', auth='user')
    def data(self, date_from=None, date_to=None, user_id=None):
        """Retorna contagem distinta de leads por estágio, com filtros"""
        domain = []
        if date_from:
            domain.append(('date_stage_change', '>=', date_from))
        if date_to:
            domain.append(('date_stage_change', '<=', date_to))
        if user_id:
            domain.append(('user_id', '=', int(user_id)))

        stages = [
            "Novo",
            "Primeiro Contato",
            "Qualificando",
            "Agendado",
            "Análise",
            "Aprovado",
            "Venda Fechada",
        ]

        counts = {}
        Stage = request.env['crm.stage'].sudo()
        Hist = request.env['crm.lead.stage.history'].sudo()

        for name in stages:
            stage = Stage.search([('name', '=', name)], limit=1)
            if not stage:
                counts[name] = 0
                continue

            # Usar read_group para contar DISTINCT lead_id
            data = Hist.read_group(
                domain + [('stage_id', '=', stage.id)],
                ['lead_id'],
                ['lead_id']
            )
            # Cada grupo representa um lead distinto
            cnt = len(data)
            counts[name] = cnt

        return {'counts': counts}
