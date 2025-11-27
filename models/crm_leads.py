from odoo import models, fields

class CrmLead(models.Model):
    _inherit = "crm.lead"

    sales_unit_id = fields.Many2one(
        "crm.sales.unit",
        related="user_id.sales_unit_id",
        store=True,
        index=True
    )
