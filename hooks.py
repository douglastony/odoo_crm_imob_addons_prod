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
