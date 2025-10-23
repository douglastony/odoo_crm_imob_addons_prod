from odoo import models, fields, api

class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescreve o método create para garantir que o user_id seja
        definido como o usuário logado se não for fornecido.
        """
        for vals in vals_list:
            if "user_id" not in vals or not vals["user_id"]:
                vals["user_id"] = self.env.user.id
        
        return super().create(vals_list)