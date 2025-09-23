# crm_sales_unit/models/res_users.py
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        string="Unidade de Vendas"
    )

    @api.model_create_multi
    def create(self, vals_list):
        users = self.env['res.users']
        creator = self.env.user  # quem está criando
        creator_unit = creator.sales_unit_id

        for vals in vals_list:
            target_unit_id = vals.get("sales_unit_id")

            # Verificação inicial: só líderes podem criar
            if not (
                creator.has_group("crm_sales_unit.group_coordinator")
                or creator.has_group("crm_sales_unit.group_manager")
                or creator.has_group("crm_sales_unit.group_director")
                or creator.has_group("crm_sales_unit.group_president")
            ):
                raise UserError("Você não tem permissão para criar usuários.")

            # Se criador não for Sócio e não tiver unidade → bloqueia
            if not creator_unit and not creator.has_group("crm_sales_unit.group_president"):
                raise UserError("Você precisa estar vinculado a uma Unidade de Vendas para criar usuários.")

            # ========================
            # COORDENADOR
            # ========================
            if creator.has_group("crm_sales_unit.group_coordinator"):
                vals["sales_unit_id"] = creator_unit.id

            # ========================
            # GERENTE
            # ========================
            elif creator.has_group("crm_sales_unit.group_manager"):
                target_unit = self.env["crm.sales.unit"].browse(target_unit_id) if target_unit_id else creator_unit
                allowed_units = creator_unit.child_ids.ids + [creator_unit.id]
                if target_unit.id not in allowed_units:
                    raise UserError("Gerente só pode criar usuários na sua gerência ou coordenações abaixo dela.")
                vals["sales_unit_id"] = target_unit.id

            # ========================
            # DIRETOR
            # ========================
            elif creator.has_group("crm_sales_unit.group_director"):
                target_unit = self.env["crm.sales.unit"].browse(target_unit_id) if target_unit_id else creator_unit
                allowed_units = creator_unit.search([("id", "child_of", creator_unit.id)]).ids
                if target_unit.id not in allowed_units:
                    raise UserError("Diretor só pode criar usuários em sua diretoria ou subunidades abaixo dela.")
                vals["sales_unit_id"] = target_unit.id

            # ========================
            # PRESIDENTE (SÓCIO)
            # ========================
            elif creator.has_group("crm_sales_unit.group_president"):
                if not target_unit_id and creator_unit:
                    vals["sales_unit_id"] = creator_unit.id

            # Criação
            user = super(ResUsers, self).create([vals])
            user._check_unique_sales_unit_role()
            users |= user

            # Log para auditoria
            _logger.info(
                "Usuário [%s] criou um novo usuário [%s] na Unidade de Vendas ID [%s]",
                creator.login,
                vals.get("login", "sem_login"),
                vals.get("sales_unit_id")
            )
        return users

    def write(self, vals):
        res = super().write(vals)
        self._check_unique_sales_unit_role()
        return res

    def _check_unique_sales_unit_role(self):
        """Impede que o usuário acumule cargos ao criar ou atualizar"""
        role_groups = [
            self.env.ref("crm_sales_unit.group_coordinator", raise_if_not_found=False),
            self.env.ref("crm_sales_unit.group_manager", raise_if_not_found=False),
            self.env.ref("crm_sales_unit.group_director", raise_if_not_found=False),
            self.env.ref("crm_sales_unit.group_president", raise_if_not_found=False),
        ]
        role_group_ids = [g.id for g in role_groups if g]

        for user in self:
            cargos = user.groups_id.filtered(lambda g: g.id in role_group_ids)
            if len(cargos) > 1:
                raise ValidationError(
                    f"O usuário {user.name} não pode ter múltiplos cargos "
                    f"(atualmente: {', '.join(cargos.mapped('name'))}). "
                    f"Selecione apenas um."
                )
