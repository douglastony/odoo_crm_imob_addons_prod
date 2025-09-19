# crm_sales_unit/models/res_users.py
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = "res.users"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        string="Unidade de Vendas"
    )
