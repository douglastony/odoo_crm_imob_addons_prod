import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    # ============================
    # CAMPOS
    # ============================
    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        string="Unidade de Vendas",
        ondelete="set null"
    )

    allowed_user_ids = fields.Many2many(
        "res.users",
        "res_users_allowed_rel",
        "user_id",
        "allowed_id",
        string="Usuários visíveis",
        compute="_compute_allowed_user_ids",
        store=True
    )

    # 🔹 Controle do round robin
    last_lead_assigned_at = fields.Datetime(
        string="Última distribuição de lead",
        default=False
    )

    # 🔹 Controle de presença (check-in)
    is_checked_in = fields.Boolean(
        string="Disponível para distribuição",
        default=False
    )

    # ============================
    # VISIBILIDADE DE LEADS
    # ============================
    @api.depends(
        "sales_unit_id",
        "sales_unit_id.child_ids",
        "sales_unit_id.parent_id",
        "sales_unit_id.member_ids",
        "sales_unit_id.responsible_id",
    )
    def _compute_allowed_user_ids(self):
        for user in self:
            allowed = user  # sempre inclui o próprio

            if user.sales_unit_id:
                descendant_units = self.env["crm.sales.unit"].search([
                    ("id", "child_of", user.sales_unit_id.id)
                ])
                ancestor_units = self.env["crm.sales.unit"].search([
                    ("id", "parent_of", user.sales_unit_id.id)
                ])
                all_units = descendant_units | ancestor_units | user.sales_unit_id

                allowed |= all_units.mapped("member_ids")
                allowed |= all_units.mapped("responsible_id")

            user.allowed_user_ids = allowed

    # ============================
    # CREATE / WRITE
    # ============================
    @api.model_create_multi
    def create(self, vals_list):
        users = self.env['res.users']
        creator = self.env.user
        creator_unit = creator.sales_unit_id

        for vals in vals_list:
            target_unit_id = vals.get("sales_unit_id")

            # 🔒 Permissões: só líderes criam
            if not (
                creator.has_group("crm_sales_unit.group_coordinator")
                or creator.has_group("crm_sales_unit.group_manager")
                or creator.has_group("crm_sales_unit.group_director")
                or creator.has_group("crm_sales_unit.group_president")
            ):
                raise UserError("Você não tem permissão para criar usuários.")

            if not creator_unit and not creator.has_group("crm_sales_unit.group_president"):
                raise UserError("Você precisa estar vinculado a uma Unidade de Vendas para criar usuários.")

            # ========================
            # Regras hierárquicas
            # ========================
            if creator.has_group("crm_sales_unit.group_coordinator"):
                vals["sales_unit_id"] = creator_unit.id

            elif creator.has_group("crm_sales_unit.group_manager"):
                target_unit = self.env["crm.sales.unit"].browse(target_unit_id) if target_unit_id else creator_unit
                allowed_units = creator_unit.child_ids.ids + [creator_unit.id]
                if target_unit.id not in allowed_units:
                    raise UserError("Gerente só pode criar usuários na sua gerência ou coordenações abaixo dela.")
                vals["sales_unit_id"] = target_unit.id

            elif creator.has_group("crm_sales_unit.group_director"):
                target_unit = self.env["crm.sales.unit"].browse(target_unit_id) if target_unit_id else creator_unit
                allowed_units = creator_unit.search([("id", "child_of", creator_unit.id)]).ids
                if target_unit.id not in allowed_units:
                    raise UserError("Diretor só pode criar usuários em sua diretoria ou subunidades abaixo dela.")
                vals["sales_unit_id"] = target_unit.id

            elif creator.has_group("crm_sales_unit.group_president"):
                if not target_unit_id and creator_unit:
                    vals["sales_unit_id"] = creator_unit.id

            # Criação real
            user = super(ResUsers, self).create([vals])
            user._check_unique_sales_unit_role()

            # 🔗 Bind automático no lado da unidade
            if user.sales_unit_id and user not in user.sales_unit_id.member_ids:
                user.sales_unit_id.write({'member_ids': [(4, user.id)]})

            users |= user

            _logger.info(
                "Usuário [%s] criou [%s] vinculado à Unidade [%s]",
                creator.login, user.login, user.sales_unit_id.display_name
            )

        return users

    def write(self, vals):
        if self.env.user.id == SUPERUSER_ID:
            return super().write(vals)

        if "sales_unit_id" in vals:
            mover = self.env.user
            mover_unit = mover.sales_unit_id
            target_unit = self.env["crm.sales.unit"].browse(vals["sales_unit_id"]) if vals["sales_unit_id"] else False

            for user in self:
                # 🔒 Regras hierárquicas
                if mover.has_group("crm_sales_unit.group_coordinator"):
                    raise AccessError(_("Coordenador não pode mover usuários entre unidades."))

                elif mover.has_group("crm_sales_unit.group_manager"):
                    allowed_units = mover_unit.child_ids.ids + [mover_unit.id]
                    if target_unit and target_unit.id not in allowed_units:
                        raise AccessError(_("Gerente só pode mover usuários dentro da sua gerência ou coordenações abaixo dela."))

                elif mover.has_group("crm_sales_unit.group_director"):
                    allowed_units = mover_unit.search([("id", "child_of", mover_unit.id)]).ids
                    if target_unit and target_unit.id not in allowed_units:
                        raise AccessError(_("Diretor só pode mover usuários dentro da sua diretoria ou descendentes."))

                elif mover.has_group("crm_sales_unit.group_president"):
                    pass  # Sócio → sem restrição

                else:
                    raise AccessError(_("Você não tem permissão para alterar a unidade de vendas de usuários."))

        res = super().write(vals)

        # 🔗 Atualiza members automaticamente
        if "sales_unit_id" in vals:
            for user in self:
                old_units = self.env["crm.sales.unit"].search([("member_ids", "in", user.id)])
                for unit in old_units:
                    if unit != user.sales_unit_id:
                        unit.write({'member_ids': [(3, user.id)]})

                if user.sales_unit_id and user not in user.sales_unit_id.member_ids:
                    user.sales_unit_id.write({'member_ids': [(4, user.id)]})

                _logger.info(
                    "Usuário [%s] movido para Unidade [%s]",
                    user.login,
                    user.sales_unit_id.display_name if user.sales_unit_id else "Nenhuma"
                )

        self._check_unique_sales_unit_role()
        return res

    # ============================
    # REGRAS
    # ============================
    def _check_unique_sales_unit_role(self):
        """Impede múltiplos cargos"""
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
