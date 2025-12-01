# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    # ======================================================
    # CAMPOS ADICIONAIS
    # ======================================================
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

    # ======================================================
    # CÁLCULO DE USUÁRIOS VISÍVEIS
    # ======================================================
    @api.depends(
        "sales_unit_id",
        "sales_unit_id.child_ids",
        "sales_unit_id.member_ids",
        "sales_unit_id.responsible_id",
        "groups_id"
    )
    @api.depends("sales_unit_id", "groups_id")
    def _compute_allowed_user_ids(self):
        for user in self:
            allowed_users = self.env["res.users"]
            allowed_users |= user  # sempre inclui o próprio

            if user.has_group("crm_sales_unit.group_president"):
                allowed_users = self.env["res.users"].search([])
            else:
                responsible_for_unit = self.env["crm.sales.unit"].search([
                    ("responsible_id", "=", user.id)
                ], limit=1, order="type desc")

                if responsible_for_unit:
                    descendant_units = self.env["crm.sales.unit"].search([
                        ("id", "child_of", responsible_for_unit.id)
                    ])
                    allowed_users |= descendant_units.mapped("member_ids")
                    allowed_users |= descendant_units.mapped("responsible_id")

            user.allowed_user_ids = allowed_users


    # ======================================================
    # CRIAÇÃO DE USUÁRIO COM PADRONIZAÇÃO E TOKEN
    # ======================================================
    @api.model_create_multi
    def create(self, vals_list):
        users = self.env["res.users"]
        creator = self.env.user
        creator_unit = creator.sales_unit_id

        # Grupos seguros padronizados
        safe_group_ids = [
            self.env.ref('base.group_user').id,
            self.env.ref('sales_team.group_sale_salesman').id,
            self.env.ref('base.group_partner_manager').id,
            self.env.ref('base.group_multi_currency').id,
            self.env.ref('mail.group_mail_canned_response_admin').id,
            self.env.ref('mail.group_mail_notification_type_inbox').id,
            self.env.ref('base.group_no_one').id,
        ]

        for vals in vals_list:
            target_unit_id = vals.get("sales_unit_id")

            # 🔐 Apenas líderes podem criar
            if not (
                creator.has_group("crm_sales_unit.group_coordinator")
                or creator.has_group("crm_sales_unit.group_manager")
                or creator.has_group("crm_sales_unit.group_director")
                or creator.has_group("crm_sales_unit.group_president")
            ):
                raise UserError(_("Você não tem permissão para criar usuários."))

            if not creator_unit and not creator.has_group("crm_sales_unit.group_president"):
                raise UserError(_("Você precisa estar vinculado a uma Unidade de Vendas para criar usuários."))

            # 📊 Hierarquia de criação
            if creator.has_group("crm_sales_unit.group_coordinator"):
                vals["sales_unit_id"] = creator_unit.id

            elif creator.has_group("crm_sales_unit.group_manager"):
                target_unit = self.env["crm.sales.unit"].browse(target_unit_id) if target_unit_id else creator_unit
                allowed_units = creator_unit.child_ids.ids + [creator_unit.id]
                if target_unit.id not in allowed_units:
                    raise UserError(_("Gerente só pode criar usuários na sua gerência ou coordenações abaixo dela."))
                vals["sales_unit_id"] = target_unit.id

            elif creator.has_group("crm_sales_unit.group_director"):
                target_unit = self.env["crm.sales.unit"].browse(target_unit_id) if target_unit_id else creator_unit
                allowed_units = creator_unit.search([("id", "child_of", creator_unit.id)]).ids
                if target_unit.id not in allowed_units:
                    raise UserError(_("Diretor só pode criar usuários em sua diretoria ou subunidades abaixo dela."))
                vals["sales_unit_id"] = target_unit.id

            elif creator.has_group("crm_sales_unit.group_president"):
                if not target_unit_id and creator_unit:
                    vals["sales_unit_id"] = creator_unit.id

            # ✅ Padroniza permissões seguras
            vals["groups_id"] = [(6, 0, safe_group_ids)]
            vals["share"] = False
            vals["active"] = True
            vals["company_id"] = self.env.company.id
            vals["company_ids"] = [(6, 0, [self.env.company.id])]

            # Cria usuário com sudo (ignora hierarquia do Administrator)
            user = super(ResUsers, self.sudo()).create([vals])
            user._check_unique_sales_unit_role()

            # 🔗 Vincula na unidade
            if user.sales_unit_id and user not in user.sales_unit_id.member_ids:
                user.sales_unit_id.write({'member_ids': [(4, user.id)]})

            users |= user

            # 🔑 Gera token de convite com superusuário
            try:
                user_with_super = self.env['res.users'].sudo().browse(user.id)
                user_with_super._signup_create_token()
                _logger.info("Token de convite gerado com superusuário para [%s]", user.login)
            except Exception as e:
                _logger.warning("Falha ao gerar token de convite para [%s]: %s", user.login, e)

            _logger.info(
                "Usuário [%s] criou [%s] com grupos padronizados e unidade [%s]",
                creator.login, user.login, user.sales_unit_id.display_name
            )

        # ✅ Recompute seguro (ignora hierarquia, inclusive Administrator id=2)
        self.env['res.users'].sudo().search([])._compute_allowed_user_ids()

        return users


    # ======================================================
    # UPDATE DE USUÁRIO COM HIERARQUIA E SEGURANÇA
    # ======================================================
    def write(self, vals):
        """Controla atualização de usuários com base na hierarquia"""
        # Bypass para persistência de campo computado (recompute automático do Odoo)
        # Se o write está apenas gravando allowed_user_ids, não validar hierarquia.
        if set(vals.keys()) == {"allowed_user_ids"}:
            return super().write(vals)

        # ✅ Superusuário sempre pode
        if self.env.user.id == SUPERUSER_ID:
            return super().write(vals)

        # ✅ Permite redefinição de senha via convite (sem autenticação)
        invite_fields = {'password', 'signup_token', 'signup_type', 'signup_expiration'}
        if set(vals.keys()).issubset(invite_fields):
            return super().write(vals)

        # ✅ Permite autoatualização segura (usuário autenticado editando a si mesmo)
        if all(user.id == self.env.user.id for user in self) and len(self) == 1:
            return super().write(vals)

        mover = self.env.user
        mover_unit = mover.sales_unit_id

        # 🔒 Verifica se é um líder autorizado
        if not (
            mover.has_group("crm_sales_unit.group_president")
            or mover.has_group("crm_sales_unit.group_director")
            or mover.has_group("crm_sales_unit.group_manager")
            or mover.has_group("crm_sales_unit.group_coordinator")
        ):
            raise AccessError(_("Você não tem permissão para editar usuários."))

        # 🧭 Determina as unidades sob gestão
        if mover.has_group("crm_sales_unit.group_president"):
            allowed_units = self.env["crm.sales.unit"].search([])
        elif mover.has_group("crm_sales_unit.group_director"):
            allowed_units = self.env["crm.sales.unit"].search([("id", "child_of", mover_unit.id)])
        elif mover.has_group("crm_sales_unit.group_manager"):
            allowed_units = mover_unit.child_ids | mover_unit
        elif mover.has_group("crm_sales_unit.group_coordinator"):
            allowed_units = mover_unit
        else:
            allowed_units = self.env["crm.sales.unit"]

        # 🔍 Filtra recordset: ignora Administrator e usuários fora da hierarquia
        users_to_check = self.filtered(
            lambda u: u.id != SUPERUSER_ID and u.sales_unit_id and u.sales_unit_id in allowed_units
        )

        # Se a operação não é apenas persistência de campo computado, bloquear fora da hierarquia
        invalid_users = (self - users_to_check).filtered(lambda u: u.id != SUPERUSER_ID)
        if invalid_users:
            raise AccessError(_(
                "Você não pode alterar os usuários fora da sua hierarquia: %s"
            ) % ", ".join(invalid_users.mapped("name")))

        # 🔐 Força grupos seguros (em qualquer update do campo groups_id)
        safe_group_ids = [
            self.env.ref('base.group_user').id,
            self.env.ref('sales_team.group_sale_salesman').id,
            self.env.ref('base.group_partner_manager').id,
            self.env.ref('base.group_multi_currency').id,
            self.env.ref('mail.group_mail_canned_response_admin').id,
            self.env.ref('mail.group_mail_notification_type_inbox').id,
            self.env.ref('base.group_no_one').id,
        ]
        if "groups_id" in vals:
            vals["groups_id"] = [(6, 0, safe_group_ids)]

        # 🧩 Valida movimentação de unidade
        target_unit_id = vals.get("sales_unit_id")
        if target_unit_id:
            target_unit = self.env["crm.sales.unit"].browse(target_unit_id)
            if target_unit not in allowed_units:
                raise AccessError(_(
                    "Você não pode mover usuários para a unidade '%s', pois ela está fora da sua hierarquia."
                ) % target_unit.display_name)

        # 💾 Aplica alterações seguras apenas nos usuários válidos
        res = super(ResUsers, users_to_check).write(vals)

        # 🔄 Atualiza vínculo com unidade
        if "sales_unit_id" in vals:
            for user in users_to_check:
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

        # 🔎 Verifica cargos exclusivos
        users_to_check._check_unique_sales_unit_role()

        # ✅ Recompute da visibilidade para todos os envolvidos na hierarquia do mover
        affected_users = users_to_check | mover

        # Inclui todos os gestores e membros sob as unidades que o gestor controla
        affected_units = allowed_units
        affected_users |= affected_units.mapped("responsible_id")
        affected_users |= affected_units.mapped("member_ids")

        # 🔄 Se houve movimentação de unidade, também recalcular gestores acima do novo destino
        if "sales_unit_id" in vals:
            target_unit = self.env["crm.sales.unit"].browse(vals["sales_unit_id"])
            while target_unit:
                if target_unit.responsible_id:
                    affected_users |= target_unit.responsible_id
                target_unit = target_unit.parent_id
                # Para não subir além do gestor que moveu
                if target_unit and target_unit.responsible_id == mover:
                    break

        # Força recompute com bypass de hierarquia
        affected_users.with_context(skip_hierarchy_check=True)._compute_allowed_user_ids()

        _logger.info(
            "Campo allowed_user_ids recalculado para %s usuários (afetados + gestores envolvidos na movimentação feita por %s).",
            len(affected_users), mover.name
)
        return res

    # ======================================================
    # VERIFICAÇÃO DE CARGOS EXCLUSIVOS
    # ======================================================
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
