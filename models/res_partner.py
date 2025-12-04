# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"

    # Relação inversa: todos os leads vinculados a este contato
    lead_ids = fields.One2many(
        "crm.lead",
        "partner_id",
        string="Leads"
    )
