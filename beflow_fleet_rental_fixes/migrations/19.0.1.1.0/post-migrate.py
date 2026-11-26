# -*- coding: utf-8 -*-
"""Enlaza cada reserva con su contrato y borra las huérfanas (4.4).

Las reservas solo nacen al confirmar un contrato (no hay vista para crearlas a
mano), así que una reserva sin contrato o sin vehículo es un resto de un borrado
y bloquea fechas que ya están libres.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE rental_fleet_reserved AS reservation
           SET contract_id = contract.id
          FROM car_rental_contract AS contract
         WHERE contract.reserved_fleet_id = reservation.id
           AND reservation.contract_id IS NULL
    """)
    _logger.info("Reservas enlazadas con su contrato: %s", cr.rowcount)
    cr.execute("DELETE FROM rental_fleet_reserved WHERE contract_id IS NULL OR reserved_obj_id IS NULL")
    _logger.info("Reservas huérfanas borradas: %s", cr.rowcount)
