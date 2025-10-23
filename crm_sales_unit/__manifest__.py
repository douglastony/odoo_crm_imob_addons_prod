{
    'name': 'CRM Sales Unit',
    'version': '1.0',
    'category': 'CRM',
    'summary': 'Hierarquia de vendas para controle de visibilidade no CRM',
    'description': """
Módulo customizado para implementar hierarquia de unidades de vendas
(Presidência, Diretoria, Gerência, Coordenação).

- Define modelo crm.sales_unit
- Estende res.users com unidade de vendas e superior
- Regras de visibilidade no CRM baseadas na hierarquia
    """,
    'author': 'Ai.Facilita',
    'website': 'https://aifacilita.com.br',
    'license': 'LGPL-3',
    'depends': [
        'crm',
        'base',
        'calendar'
    ],
        'data': [
        'security/sales_unit_groups.xml',   # cria os grupos primeiro
        'security/ir.model.access.csv',     # depois aplica regras de acesso
        'security/crm_lead_rules.xml',
        "security/calendar_event_rules.xml",
        'views/crm_lead_kanban_custom.xml',
        'views/crm_sales_unit_views.xml',   # só então views/menus
        'views/res_users_views.xml',   # <-- novo        
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}