# crm_sales_unit/models/res_users.py
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

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

            # Log para auditoria
            _logger.info(
                "Usuário [%s] criou um novo usuário [%s] na Unidade de Vendas ID [%s]",
                creator.login,
                vals.get("login", "sem_login"),
                vals.get("sales_unit_id")
            )

            users |= super(ResUsers, self).create([vals])

        return users
