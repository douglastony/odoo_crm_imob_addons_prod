# -*- coding: utf-8 -*-
from odoo import models, fields

class CRMSalesUnit(models.Model):
    _name = "crm.sales.unit"
    _description = "Unidade de Vendas (CRM)"
    _parent_store = True
    _parent_name = "parent_id"

    name = fields.Char(string="Nome", required=True)
    type = fields.Selection(
        [
            ('presidencia', 'Presidência'),
            ('diretoria', 'Diretoria'),
            ('gerencia', 'Gerência'),
            ('coordenacao', 'Coordenação'),
        ],
        string="Tipo de Unidade",
        required=True
    )

    # Hierarquia
    parent_id = fields.Many2one(
        "crm.sales.unit",
        string="Unidade Superior",
        index=True,
        ondelete="cascade"
    )
    child_ids = fields.One2many(
        "crm.sales.unit",
        "parent_id",
        string="Subunidades"
    )
    parent_path = fields.Char(index=True)

    # Usuários
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsável da Unidade",
        required=True
    )
    member_ids = fields.Many2many(
        "res.users",
        string="Membros (Corretores)"
    )

    # Status
    active = fields.Boolean(default=True)

