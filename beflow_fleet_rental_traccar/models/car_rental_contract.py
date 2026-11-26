# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import format_datetime


class CarRentalContract(models.Model):
    """Rellena las horas de motor vacías de los contratos por horas con la lectura del GPS."""
    _inherit = "car.rental.contract"

    def action_run(self):
        result = super().action_run()
        for contract in self.filtered("rent_by_hour"):
            contract._fill_engine_hours_from_gps("engine_hours_start")
        return result

    def action_verify(self):
        for contract in self.filtered("rent_by_hour"):
            contract._fill_engine_hours_from_gps("engine_hours_end")
        return super().action_verify()

    def _fill_engine_hours_from_gps(self, field_name):
        """Un valor puesto a mano nunca se pisa; una lectura menor que la inicial (GPS cambiado) se ignora."""
        device = self.vehicle_id.traccar_device_ids[:1]
        reading = device.engine_hours
        if self[field_name] or reading <= 0 or reading < self.engine_hours_start:
            return
        self[field_name] = reading
        self.message_post(body=self.env._(
            "Engine hours %(hours)s taken from GPS (position of %(when)s).",
            hours=reading, when=format_datetime(self.env, device.position_time)))
