# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.addons.fleet_traccar.models.traccar import number, timestamp

MS_PER_HOUR = 3_600_000


class TraccarDevice(models.Model):
    _inherit = "traccar.device"

    engine_hours = fields.Float(string="Engine hours", readonly=True)

    def _apply_position(self, position):
        """fleet_traccar ignora las posiciones más antiguas que la última: las horas siguen la misma regla."""
        super()._apply_position(position)
        when = timestamp(position.get("fixTime"))
        hours_ms = number((position.get("attributes") or {}).get("hours"))
        if when and self.position_time == when and hours_ms is not None and hours_ms >= 0:
            self.engine_hours = hours_ms / MS_PER_HOUR
