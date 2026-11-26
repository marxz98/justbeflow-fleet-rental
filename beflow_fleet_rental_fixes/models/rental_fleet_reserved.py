# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RentalFleetReserved(models.Model):
    """La reserva pertenece a su contrato y a su vehículo (4.4).

    fleet_rental solo enlaza contrato -> reserva y deja `reserved_obj_id` en
    `set null`: borrar el contrato o el vehículo dejaba reservas huérfanas que
    seguían bloqueando fechas.
    """
    _inherit = "rental.fleet.reserved"

    contract_id = fields.Many2one(
        "car.rental.contract", string="Contract", ondelete="cascade", index=True, readonly=True)
    reserved_obj_id = fields.Many2one(ondelete="cascade", index=True)

    @api.model
    def _overlapping(self, vehicle, date_from, date_to, exclude=None):
        """Reservas del vehículo que comparten al menos un día con el rango (ambos extremos incluidos)."""
        domain = [
            ("reserved_obj_id", "=", vehicle.id),
            ("date_from", "<=", date_to),
            ("date_to", ">=", date_from),
        ]
        if exclude:
            domain.append(("id", "not in", exclude.ids))
        return self.search(domain, order="date_from")
