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
        """Valida IP e localização.
        - Se houver locais configurados: exige latitude/longitude e valida se está dentro do raio.
        - Se não houver locais: não bloqueia por localização.
        - Se houver ranges de IP: valida IP.
        """
        ctx = {}

        # IP do cliente
        client_ip = self._get_client_ip()
        ctx['client_ip'] = client_ip

        ip_recs = self.env['crm.sales.unit.ip'].search([])
        if ip_recs:  # só valida se houver ranges configurados
            if not client_ip:
                _logger.warning("Check-in NEGADO: IP do cliente não identificado.")
                raise ValidationError(_("Check-in negado. Não foi possível identificar seu IP."))
            try:
                ip_obj = ipaddress.ip_address(client_ip)
            except ValueError:
                _logger.warning("Check-in NEGADO: IP inválido detectado (%s).", client_ip)
                raise ValidationError(_("IP inválido detectado (%s).") % client_ip)
            matched = False
            for ip_rec in ip_recs:
                if ip_obj in ipaddress.ip_network(ip_rec.cidr, strict=False):
                    ctx['validated_ip_rec'] = ip_rec
                    matched = True
                    _logger.info("IP VALIDADO: %s dentro do range %s", client_ip, ip_rec.cidr)
                    break
            if not matched:
                _logger.warning("Check-in NEGADO: IP %s fora de todos os ranges permitidos.", client_ip)
                raise ValidationError(_("Check-in negado. Seu IP (%s) não está em nenhum range permitido.") % client_ip)

        # Localização
        raw_lat = self.env.context.get('latitude') or getattr(request, 'params', {}).get('latitude')
        raw_lon = self.env.context.get('longitude') or getattr(request, 'params', {}).get('longitude')

        locs = self.env['crm.sales.unit.location'].search([])
        validated_location = False
        latitude = None
        longitude = None

        _logger.warning("Validando check-in: lat=%s lon=%s ip=%s", raw_lat, raw_lon, client_ip)

        if locs:  # só valida se houver locais configurados
            if raw_lat is None or raw_lon is None:
                _logger.warning("Check-in NEGADO: coordenadas não informadas.")
                raise ValidationError(_("Check-in negado. Coordenadas de localização não foram informadas."))
            try:
                latitude = float(str(raw_lat).replace(',', '.'))
                longitude = float(str(raw_lon).replace(',', '.'))
            except Exception:
                _logger.warning("Check-in NEGADO: coordenadas inválidas. lat=%s lon=%s", raw_lat, raw_lon)
                raise ValidationError(_("Coordenadas inválidas para check-in/out."))

            # Avalia cada localização e loga a distância
            for loc in locs:
                dist = self._calculate_distance(latitude, longitude, loc.latitude, loc.longitude)
                _logger.info("Distância até %s: %.2f m (raio %.2f)", loc.name, dist, loc.radius)
                if dist <= loc.radius:
                    validated_location = loc
                    ctx['validated_location'] = loc
                    _logger.info("Check-in VALIDADO por localização: %s (%.2f m dentro do raio %.2f)",
                                loc.name, dist, loc.radius)
                    break

            if not validated_location:
                nearest = min(
                    locs,
                    key=lambda loc: self._calculate_distance(latitude, longitude, loc.latitude, loc.longitude)
                )
                nearest_dist = self._calculate_distance(latitude, longitude, nearest.latitude, nearest.longitude)
                _logger.warning("Check-in NEGADO: mais próximo '%s' (%.2f m, raio %.2f)",
                                nearest.name, nearest_dist, nearest.radius)
                raise ValidationError(_(
                    "Check-in negado. Você está a %.2f metros do local '%s'. "
                    "Distância máxima permitida: %.2f metros."
                ) % (nearest_dist, nearest.name, nearest.radius))

        ctx['latitude'] = latitude
        ctx['longitude'] = longitude
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
