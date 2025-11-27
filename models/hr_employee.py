# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, time
from odoo.exceptions import ValidationError
import logging
import pytz

_logger = logging.getLogger(__name__)

class HREmployee(models.Model):
    _inherit = "hr.employee"

    # ======================================================
    # VISIBILIDADE DE FUNCIONÁRIOS
    # ======================================================
    can_be_seen = fields.Boolean(
        string="Pode ser visto",
        compute="_compute_visibility",
        store=False
    )

    @api.depends("user_id")
    def _compute_visibility(self):
        """Define se o funcionário pode ser visto pelo usuário atual"""
        for emp in self:
            if emp.user_id and emp.user_id in self.env.user.allowed_user_ids:
                emp.can_be_seen = True
            else:
                emp.can_be_seen = False

    # ======================================================
    # AÇÕES DE CHECK-IN/OUT
    # ======================================================
    def attendance_action_change(self):
        ctx = self._validate_checkin_conditions()
        res = super().attendance_action_change()
        self._write_attendance_extras(res, ctx)

        config = self.env['crm.sales.unit.config'].get_config()
        if not config:
            return res

        now_utc = fields.Datetime.now()
        # converter start_time para UTC
        tz = pytz.timezone('America/Sao_Paulo')
        start_hour = int(config.start_time)
        start_min  = int(round((config.start_time - start_hour) * 60))
        start_dt_local = now_utc.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        start_dt_utc = tz.localize(start_dt_local).astimezone(pytz.UTC).replace(tzinfo=None)

        attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_out', '=', False)
        ], order='check_in desc', limit=1)

        if attendance and not attendance.check_out and now_utc < start_dt_utc:
            queue = self.env['crm.sales.unit.queue'].search([
                ('employee_id', '=', self.id),
                ('date', '=', fields.Date.context_today(self))
            ], limit=1)
            if not queue:
                self.env['crm.sales.unit.queue'].create({
                    'user_id': self.user_id.id,
                    'employee_id': self.id,
                    'checkin_time': attendance.check_in,  # preferir o horário real (UTC)
                    'date': fields.Date.today(),
                    'active': True,
                })
                _logger.info("Funcionário %s entrou na fila de leads", self.name)

        elif attendance and attendance.check_out:
            queue = self.env['crm.sales.unit.queue'].search([
                ('employee_id', '=', self.id),
                ('active', '=', True)
            ])
            if queue:
                queue.unlink()
                _logger.info("Funcionário %s removido da fila no checkout", self.name)

        return res
    
    def populate_queue_start_of_day(self):
        """Coloca na fila funcionários logados após 9h locais e antes do início do expediente"""
        config = self.env['crm.sales.unit.config'].get_config()
        if not config:
            return

        tz = pytz.timezone('America/Sao_Paulo')
        now_utc = fields.Datetime.now()

        # calcular limites
        start_hour = int(config.start_time)
        start_min = int(round((config.start_time - start_hour) * 60))
        start_dt_local = now_utc.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        start_dt_utc = tz.localize(start_dt_local).astimezone(pytz.UTC).replace(tzinfo=None)

        nine_local = now_utc.replace(hour=9, minute=0, second=0, microsecond=0)
        nine_utc = tz.localize(nine_local).astimezone(pytz.UTC).replace(tzinfo=None)

        employees = self.search([('user_id', '!=', False)])
        for emp in employees:
            att = self.env['hr.attendance'].search([
                ('employee_id', '=', emp.id),
                ('check_out', '=', False)
            ], order='check_in desc', limit=1)

            if not att:
                continue

            # regra: logou depois das 9h locais e antes do início do expediente
            if att.check_in >= nine_utc and att.check_in < start_dt_utc:
                queue = self.env['crm.sales.unit.queue'].search([
                    ('employee_id', '=', emp.id),
                    ('date', '=', fields.Date.context_today(self))
                ], limit=1)
                if not queue:
                    self.env['crm.sales.unit.queue'].create({
                        'user_id': emp.user_id.id,
                        'employee_id': emp.id,
                        'checkin_time': att.check_in,
                        'date': fields.Date.context_today(self),
                        'active': True,
                    })
                    _logger.info("Funcionário %s colocado na fila pelo cron", emp.name)


    # ======================================================
    # FORÇAR CHECK-OUT MANUALMENTE
    # ======================================================

    def manager_force_checkout(self):
        """Permite que gestores façam checkout manual dos subordinados"""
        user = self.env.user
        # Apenas coordenador, gerente, diretor ou presidente podem usar
        if not (user.has_group("crm_sales_unit.group_coordinator") or
                user.has_group("crm_sales_unit.group_manager") or
                user.has_group("crm_sales_unit.group_director") or
                user.has_group("crm_sales_unit.group_president")):
            raise ValidationError(_("Você não tem permissão para forçar checkout de funcionários."))

        now_utc = fields.Datetime.now()
        for emp in self:
            today = fields.Date.today()
            attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', emp.id),
                ('check_out', '=', False),
                ('check_in', '>=', today)
            ], limit=1)
            if attendance:
                attendance.write({'check_out': now_utc})
                _logger.info("Checkout manual forçado por gestor [%s] para funcionário [%s]", user.name, emp.name)

            queue = self.env['crm.sales.unit.queue'].search([
                ('employee_id', '=', emp.id),
                ('active', '=', True),
            ])
            if queue:
                queue.unlink()
                _logger.info("Funcionário %s removido da fila no checkout", self.name)

    # ======================================================
    # FORÇAR CHECK-OUT NO FIM DO EXPEDIENTE
    # ======================================================
    def force_end_of_day_checkout(self):
        config = self.env['crm.sales.unit.config'].get_config()
        if not config:
            return

        now_utc = fields.Datetime.now()
        today = fields.Date.today()

        employees = self.search([('user_id', '!=', False)])

        # converter end_time para UTC
        tz = pytz.timezone('America/Sao_Paulo')
        end_hour = int(config.end_time)
        end_min  = int(round((config.end_time - end_hour) * 60))
        end_dt_local = now_utc.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        end_dt_utc = tz.localize(end_dt_local).astimezone(pytz.UTC).replace(tzinfo=None)

        for emp in employees:
            attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', emp.id),
                ('check_out', '=', False)
            ], limit=1)

            if attendance:
                checkin_date = attendance.check_in.date()
                checkin_hour = attendance.check_in.hour

            # Regra 1: não é do dia → deslogar
            if checkin_date < today:
                attendance.write({'check_out': now_utc})
                _logger.info("Checkout forçado (dia anterior) para %s", emp.name)

            # Regra 2: do dia, mas antes das 9h → deslogar
            elif checkin_date == today and checkin_hour < 12:
                attendance.write({'check_out': now_utc})
                _logger.info("Checkout forçado (antes das 9h) para %s", emp.name)

            # Regra 3: fim do expediente → deslogar
            elif now_utc >= end_dt_utc:
                attendance.write({'check_out': now_utc})
                _logger.info("Checkout forçado (fim do expediente) para %s", emp.name)


            # Regra 4: do dia e >= 9h, mas ainda dentro do expediente → mantém logado
            else:
                _logger.info("Funcionário %s continua logado (expediente ativo)", emp.name)

            # sempre limpar fila se houver
            queue = self.env['crm.sales.unit.queue'].search([
                ('employee_id', '=', emp.id)
            ])
            if queue and now_utc >= end_dt_utc:
                queue.unlink()
                _logger.info("Funcionário %s removido da fila", emp.name)



    # ======================================================
    # REMOVER MANUALMENTE DA FILA
    # ======================================================
    def add_to_queue(self):
        """Permite ao presidente colocar manualmente funcionário na fila"""
        if not self.env.user.has_group("crm_sales_unit.group_president"):
            raise ValidationError(_("Apenas o presidente pode adicionar manualmente funcionários à fila."))
        self.env['crm.sales.unit.queue'].create({
            'user_id': self.user_id.id,
            'employee_id': self.id,
            'checkin_time': fields.Datetime.now(),
            'date': fields.Date.today(),
        })
        _logger.info("Funcionário %s adicionado manualmente à fila pelo presidente", self.name)

    
    def remove_from_queue(self):
        queue = self.env['crm.sales.unit.queue'].search([
            ('employee_id', '=', self.id),
            ('active', '=', True)
        ])
        if queue:
            queue.unlink()
            _logger.info("Funcionário %s removido da fila no checkout", self.name)

    #Remove da fila quem fez checkout
    def cleanup_queue_after_checkout(self):
        """Remove da fila quem já fez checkout"""
        now_utc = fields.Datetime.now()
        queues = self.env['crm.sales.unit.queue'].search([('active', '=', True)])
        for q in queues:
            # procura se existe attendance aberto para o funcionário
            attendance_open = self.env['hr.attendance'].search([
                ('employee_id', '=', q.employee_id.id),
                ('check_out', '=', False)
            ], limit=1)
            if not attendance_open:
                q.unlink()
                _logger.info("Funcionário %s removido da fila (checkout detectado)", q.employee_id.name)


    # ======================================================
    # GRAVAÇÃO DE EXTRAS DE ATTENDANCE
    # ======================================================
    def _write_attendance_extras(self, res, ctx):
        try:
            attendance = None
            if isinstance(res, dict):
                attendance = self.env['hr.attendance'].browse(res.get('res_id'))
            elif isinstance(res, models.Model):
                attendance = res
            if not attendance:
                _logger.warning("Attendance extras: nenhum hr.attendance encontrado (res=%s)", res)
                return

            vals = {}
            lat = ctx.get('latitude')
            lon = ctx.get('longitude')
            ip = ctx.get('client_ip')
            loc = ctx.get('validated_location')
            ip_rec = ctx.get('validated_ip_rec')

            if lat is not None and lon is not None:
                if not attendance.check_out:
                    vals.update({'check_in_latitude': lat, 'check_in_longitude': lon})
                else:
                    vals.update({'check_out_latitude': lat, 'check_out_longitude': lon})

            if ip:
                if not attendance.check_out:
                    vals['check_in_ip'] = ip
                else:
                    vals['check_out_ip'] = ip

            if loc:
                if not attendance.check_out:
                    vals['check_in_location_id'] = loc.id
                else:
                    vals['check_out_location_id'] = loc.id

            if ip_rec:
                vals['check_in_ip_id'] = ip_rec.id

            if vals:
                attendance.write(vals)
                _logger.info("Attendance extras gravados: %s", vals)
        except Exception as e:
            _logger.exception("Falha ao gravar extras de attendance: %s", e)
