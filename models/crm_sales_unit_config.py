# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.http import request
from datetime import datetime
import ipaddress
import math
import logging

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Configuração: locais, IPs permitidos, horário de expediente e Fila de leads (globais)
# ---------------------------------------------------------
class CRMSalesUnitLocation(models.Model):
    _name = "crm.sales.unit.location"
    _description = "Localização Permitida para Check-in"

    name = fields.Char(string="Nome do Local", required=True)
    latitude = fields.Float(string="Latitude", required=True, digits=(10, 7))
    longitude = fields.Float(string="Longitude", required=True, digits=(10, 7))
    radius = fields.Float(string="Raio de Tolerância (metros)", default=50.0, required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'O nome do local deve ser único!'),
    ]


class CRMSalesUnitIP(models.Model):
    _name = "crm.sales.unit.ip"
    _description = "IP ou Range Permitido para Check-in"

    cidr = fields.Char(
        string="IP ou Range (CIDR)",
        required=True,
        help="Exemplo: 177.27.6.243 para IP único ou 177.27.0.0/16 para range."
    )

    _sql_constraints = [
        ('cidr_unique', 'unique(cidr)', 'O IP ou range deve ser único!'),
    ]

    @api.constrains('cidr')
    def _check_valid_cidr(self):
        for record in self:
            try:
                ipaddress.ip_network(record.cidr, strict=False)
            except ValueError:
                raise ValidationError(_("O valor '%s' não é um IP ou range CIDR válido.") % record.cidr)


class CRMSalesUnitQueue(models.Model):
    _name = "crm.sales.unit.queue"
    _description = "Fila de Corretores para Leads"

    user_id = fields.Many2one("res.users", string="Usuário", required=True)
    employee_id = fields.Many2one("hr.employee", string="Funcionário")
    checkin_time = fields.Datetime(string="Hora de Entrada")
    active = fields.Boolean(string="Ativo na Fila", default=True)
    date = fields.Date(string="Data", default=fields.Date.today, required=True)

    def remove_from_queue(self):
        for rec in self:
            rec.active = False
            _logger.info("Registro %s removido da fila", rec.id)


# ---------------------------------------------------------
# Auditoria em hr.attendance (dados extras de check-in/out)
# ---------------------------------------------------------
class HRAttendance(models.Model):
    _inherit = "hr.attendance"

    check_in_latitude = fields.Float(string="Latitude (Check-in)", digits=(10, 7))
    check_in_longitude = fields.Float(string="Longitude (Check-in)", digits=(10, 7))
    check_in_ip = fields.Char(string="IP (Check-in)")
    check_in_location_id = fields.Many2one("crm.sales.unit.location", string="Localização Validada (Check-in)")
    check_in_ip_id = fields.Many2one("crm.sales.unit.ip", string="IP Validado (Check-in)")

    check_out_latitude = fields.Float(string="Latitude (Check-out)", digits=(10, 7))
    check_out_longitude = fields.Float(string="Longitude (Check-out)", digits=(10, 7))
    check_out_ip = fields.Char(string="IP (Check-out)")
    check_out_location_id = fields.Many2one("crm.sales.unit.location", string="Localização Validada (Check-out)")
    check_out_distance_from_location = fields.Float(string="Distância do Check-out ao Local Validado (m)")


# ---------------------------------------------------------
# Helpers em hr.employee (sem sobrescrever nativos)
# ---------------------------------------------------------
class HREmployee(models.Model):
    _inherit = "hr.employee"

    EARTH_RADIUS = 6371000.0  # metros

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return self.EARTH_RADIUS * c

    def _get_client_ip(self):
        httpreq = getattr(request, 'httprequest', None)
        if not httpreq:
            return None
        ip_address = httpreq.environ.get('HTTP_X_FORWARDED_FOR')
        if ip_address:
            return ip_address.split(',')[0].strip()
        ip_address = httpreq.environ.get('HTTP_X_REAL_IP')
        if ip_address:
            return ip_address.strip()
        return httpreq.remote_addr

    # (mantém os métodos de validação e auditoria como já estavam)
    def _validate_checkin_conditions(self):
        """Valida apenas IP e localização. 
        Não bloqueia por horário, pois isso é tratado na fila.
        """
        ctx = {}
        # IP do cliente
        client_ip = self._get_client_ip()
        ctx['client_ip'] = client_ip

        # Só valida IP se houver registros configurados
        ip_recs = self.env['crm.sales.unit.ip'].search([])
        if client_ip and ip_recs:
            # procura se o IP do cliente está dentro de algum range configurado
            matched = False
            for ip_rec in ip_recs:
                try:
                    net = ipaddress.ip_network(ip_rec.cidr, strict=False)
                    if ipaddress.ip_address(client_ip) in net:
                        ctx['validated_ip_rec'] = ip_rec
                        matched = True
                        break
                except ValueError:
                    continue
            if not matched:
                raise ValidationError(_("IP não autorizado para check-in: %s") % client_ip)

        # Localização (se disponível no contexto)
        lat = self.env.context.get('latitude')
        lon = self.env.context.get('longitude')
        ctx['latitude'] = lat
        ctx['longitude'] = lon

        if lat and lon:
            loc = self.env['crm.sales.unit.location'].search([], limit=1)
            if loc:
                dist = self._calculate_distance(lat, lon, loc.latitude, loc.longitude)
                if dist <= loc.radius:
                    ctx['validated_location'] = loc
                else:
                    raise ValidationError(_("Fora da área permitida para check-in (distância %.2fm)") % dist)

        return ctx

# ---------------------------------------------------------
# Configuração única de expediente
# ---------------------------------------------------------
class CRMSalesUnitConfig(models.Model):
    _name = "crm.sales.unit.config"
    _description = "Horário de Expediente"

    start_time = fields.Float(string="Início do Expediente", required=True, digits=(16, 2), default=13.0)
    end_time = fields.Float(string="Fim do Expediente", required=True, digits=(16, 2), default=21.0)

    @api.model_create_multi
    def create(self, vals_list):
        if self.search([]):
            raise ValidationError(_("Já existe uma configuração de expediente. Edite a existente."))
        return super().create(vals_list)

    @api.model
    def get_config(self):
        """Retorna sempre o único registro de configuração, criando se não existir"""
        config = self.search([], limit=1)
        if not config:
            config = self.create({
                'start_time': 13.0,
                'end_time': 21.0,
            })
        return config

    @api.model
    def reset_to_defaults(self):    
        """Reseta expediente para os valores padrão (13h–21h)"""
        config = self.search([], limit=1)
        if config:
            config.write({
                'start_time': 13.0,
                'end_time': 21.0,
            })
