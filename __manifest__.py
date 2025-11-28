{
    'name': 'CRM Sales Unit',
    'version': '1.0',
    'category': 'CRM',
    'summary': 'Hierarquia de vendas para controle de visibilidade no CRM',
    'description': """
Módulo customizado para implementar hierarquia de unidades de vendas
(Presidência, Diretoria, Gerência, Coordenação).

- Define modelo crm.sales.unit
- Estende res.users com unidade de vendas e superior
- Regras de visibilidade no CRM baseadas na hierarquia
    """,
    'author': 'Ai.Facilita',
    'website': 'https://aifacilita.com.br',
    'license': 'LGPL-3',
    'depends': ['crm', 'base', 'calendar', 'hr_attendance', 'web'],
    'data': [
        'security/sales_unit_groups.xml',
        'security/ir.model.access.csv',
        'security/crm_lead_rules.xml',
        'security/calendar_event_rules.xml',
        'security/crm_sales_unit_attendance_rules.xml',  # atualizado para hr.attendance
        'data/ir_cron.xml',
        'views/quick_create_opportunity_wizard_views.xml',
        'views/quick_create_opportunity_wizard_action.xml',
        'views/crm_lead_kanban_custom.xml',
        'views/crm_sales_unit_views.xml',
        'views/res_users_views.xml',
        'views/crm_sales_unit_config_views.xml',
        'views/crm_sales_unit_attendance_views.xml',  # aponta para hr.attendance
        'views/crm_lead_stage_history_views.xml',  # view pivot
        'views/crm_lead_BI_menus.xml',  # menus
    ],
    'post_init_hook': 'post_init_hook',
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
