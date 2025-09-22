# crm_sales_unit/models/res_users.py
from odoo import models, fields, api
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        string="Unidade de Vendas"
    )

    @api.model
    def create(self, vals):
        creator = self.env.user  # quem está criando o usuário
        sales_unit = creator.sales_unit_id

        if not creator.has_group("crm_sales_unit.group_coordinator") \
           and not creator.has_group("crm_sales_unit.group_manager") \
           and not creator.has_group("crm_sales_unit.group_director") \
           and not creator.has_group("crm_sales_unit.group_president"):
            raise UserError("Você não tem permissão para criar usuários.")

        # Se criador tem unidade de vendas, herda a estrutura
        if sales_unit:
            if creator.has_group("crm_sales_unit.group_coordinator"):
                # Coordenador só pode criar na própria coordenação
                vals["sales_unit_id"] = sales_unit.id

            elif creator.has_group("crm_sales_unit.group_manager"):
                # Gerente pode criar na gerência ou coordenações abaixo
                if not vals.get("sales_unit_id"):
                    vals["sales_unit_id"] = sales_unit.id
                else:
                    unit = self.env["crm.sales.unit"].browse(vals["sales_unit_id"])
                    if unit.id != sales_unit.id and unit.parent_id.id != sales_unit.id:
                        raise UserError("Gerente só pode criar usuários em sua gerência ou coordenações abaixo dela.")

            elif creator.has_group("crm_sales_unit.group_director"):
                # Diretor pode criar na diretoria ou subunidades
                allowed_units = sales_unit.child_ids + sales_unit
                if vals.get("sales_unit_id") and vals["sales_unit_id"] not in allowed_units.ids:
                    raise UserError("Diretor só pode criar usuários em sua diretoria ou subunidades.")

            elif creator.has_group("crm_sales_unit.group_president"):
                # Presidente não tem restrição
                pass

        return super().create(vals)
