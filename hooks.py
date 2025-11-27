from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Referência para a ação do pipeline
    action = env.ref('crm.crm_lead_all_leads', raise_if_not_found=False)
    # Referência para sua view customizada
    custom_view = env.ref('crm_sales_unit.crm_lead_kanban_custom', raise_if_not_found=False)

    if action and custom_view:
        # Procura se já existe um registro para essa combinação (action, kanban)
        view_link = env['ir.actions.act_window.view'].search([
            ('act_window_id', '=', action.id),
            ('view_mode', '=', 'kanban'),
        ], limit=1)

        if view_link:
            # Atualiza a view usada
            view_link.view_id = custom_view
        else:
            # Se não existir, cria a associação
            env['ir.actions.act_window.view'].create({
                'sequence': 1,
                'view_mode': 'kanban',
                'view_id': custom_view.id,
                'act_window_id': action.id,
            })


    # --- Criação dos filtros dinâmicos ---
    today = date.today()
    yesterday = today - timedelta(days=1)
    start_week = today - timedelta(days=today.weekday())
    start_last_week = start_week - timedelta(days=7)

    filters = [
        {
            'name': 'Hoje',
            'domain': [('date_last_stage_update', '=', today)],
        },
        {
            'name': 'Ontem',
            'domain': [('date_last_stage_update', '=', yesterday)],
        },
        {
            'name': 'Semana Corrente',
            'domain': [('date_last_stage_update', '>=', start_week)],
        },
        {
            'name': 'Semana Passada',
            'domain': [
                ('date_last_stage_update', '>=', start_last_week),
                ('date_last_stage_update', '<', start_week),
            ],
        },
    ]

    for f in filters:
        # Evita duplicar se já existir
        if not env['ir.filters'].search([('name', '=', f['name']), ('model_id', '=', 'crm.lead')], limit=1):
            env['ir.filters'].create({
                'name': f['name'],
                'model_id': 'crm.lead',
                'domain': f['domain'],
                'user_id': False,
            })