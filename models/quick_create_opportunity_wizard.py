# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)

class QuickCreateOpportunityWizard(models.TransientModel):
    _name = 'crm.opportunity.quick.create.wizard'
    _description = 'Assistente de criação rápida de oportunidade'

    name = fields.Char(string='Nome do Cliente', required=True)
    phone = fields.Char(string='Telefone', required=True)

    def _normalize_phone(self, phone):
        if not phone:
            return False
        cleaned = re.sub(r'\D', '', phone)
        _logger.debug("Telefone original: %s | Telefone limpo: %s", phone, cleaned)

        if len(cleaned) == 9:
            return '21' + cleaned
        elif len(cleaned) == 11:
            return cleaned
        else:
            raise ValidationError(_("O telefone deve conter 9 ou 11 dígitos."))

    def action_create_opportunity(self):
        self.ensure_one()
        _logger.info("Iniciando criação de oportunidade para: %s", self.name or "<sem nome>")

        phone_normalized = self._normalize_phone(self.phone)
        if not phone_normalized:
            _logger.warning("Telefone normalizado está vazio para: %s", self.name or "<sem nome>")
            raise ValidationError(_("O campo Telefone não pode estar vazio."))

        # checar duplicidade com telefone já padronizado
        existing = self.env['crm.lead'].search([
            ('type', '=', 'opportunity'),
            ('active', '=', True),
            ('phone', '=', phone_normalized)
        ], limit=1)
        if existing:
            resp = existing.user_id.name or _('não atribuído')
            raise ValidationError(_("Esta oportunidade está sendo tratada pelo corretor %s.") % resp)

        # cria partner com sudo
        try:
            partner_vals = {
                'name': self.name,
                'phone': phone_normalized,
                'is_company': False,
                'type': 'contact',
                'company_id': self.env.company.id,
                'company_type': 'person',
            }
            partner = self.env['res.partner'].sudo().create(partner_vals)
            _logger.info("Contato criado com ID %s", partner.id)
        except Exception as e:
            _logger.exception("Erro ao criar partner")
            raise ValidationError(_("Falha ao criar o contato. Erro: %s") % e)

        # cria oportunidade
        try:
            lead_vals = {
                'name': self.name,
                'phone': phone_normalized,
                'partner_id': partner.id,
                'type': 'opportunity',
                'user_id': self.env.uid,
            }
            lead = self.env['crm.lead'].create(lead_vals)
            _logger.info("Oportunidade criada com ID %s", lead.id)
        except Exception as e:
            _logger.exception("Erro ao criar oportunidade; tentando remover contato")
            try:
                partner.sudo().unlink()
            except Exception:
                _logger.exception("Falha ao remover contato após erro")
            raise ValidationError(_("Falha ao criar a oportunidade. Erro: %s") % e)

        return {'type': 'ir.actions.act_window_close'}
