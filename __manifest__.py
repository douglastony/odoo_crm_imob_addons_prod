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
    ],
    'data': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

