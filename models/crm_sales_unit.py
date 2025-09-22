# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class CRMSalesUnit(models.Model):
    _name = "crm.sales.unit"
    _description = "Unidade de Vendas (CRM)"
    _parent_store = True
    _parent_name = "parent_id"

    # ============================
    # CAMPOS
    # ============================

    name = fields.Char(
        string="Nome",
        required=True
    )

    type = fields.Selection(
        [
            ("presidencia", "Presidência"),
            ("diretoria", "Diretoria"),
            ("gerencia", "Gerência"),
            ("coordenacao", "Coordenação"),
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

    # ============================
    # REGRAS DE NEGÓCIO
    # ============================

    def write(self, vals):
        """Impede arquivar unidade com membros ainda ativos"""
        if "active" in vals and vals["active"] is False:
            for unit in self:
                if unit.member_ids:
                    raise UserError(
                        "Não é possível arquivar a unidade '%s' enquanto ainda houver membros associados. "
                        "Remaneje os corretores antes de arquivar." % unit.name
                    )
        res = super().write(vals)
        # Reforça validação após salvar
        self._check_unique_responsible()
        self._check_parent_unit()
        return res

    @api.constrains("responsible_id", "active")
    def _check_unique_responsible(self):
        """Garante que cada responsável só lidere uma unidade ativa por vez"""
        for unit in self:
            if unit.active and unit.responsible_id:
                conflict = self.search([
                    ("id", "!=", unit.id),
                    ("responsible_id", "=", unit.responsible_id.id),
                    ("active", "=", True),
                ], limit=1)
                if conflict:
                    raise ValidationError(
                        "O usuário %s já é responsável pela unidade '%s'. "
                        "Um responsável só pode atuar em uma unidade ativa por vez."
                        % (unit.responsible_id.name, conflict.name)
                    )

    @api.constrains("type", "parent_id")
    def _check_parent_unit(self):
        """Garante que apenas Presidência pode não ter unidade superior"""
        for unit in self:
            if unit.type != "presidencia" and not unit.parent_id:
                raise ValidationError(
                    "A unidade '%s' do tipo '%s' deve estar vinculada a uma unidade superior."
                    % (unit.name, unit.type)
                )

    def unlink(self):
        """Bloqueia qualquer exclusão de unidades"""
        raise UserError(
            "Não é permitido excluir unidades de vendas. "
            "Apenas arquive para manter o histórico intacto."
        )
