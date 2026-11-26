# -*- coding: utf-8 -*-
from odoo import models


class FleetVehicle(models.Model):
    """Unicidad de VIN y placa en fleet.vehicle.

    fleet_rental 19.0.1.0.1 las declara con `_sql_constraints`, que Odoo 19
    ignora con un WARNING. Aquí se replican con la API vigente
    (models.Constraint), sin modificar el código upstream.

    PostgreSQL permite múltiples NULL en una columna UNIQUE, por lo que los
    vehículos sin VIN ni placa no quedan bloqueados.
    """
    _inherit = 'fleet.vehicle'

    _vin_sn_unique = models.Constraint(
        'UNIQUE(vin_sn)',
        'Chassis Number already exists!')
    _license_plate_unique = models.Constraint(
        'UNIQUE(license_plate)',
        'License plate already exists!')
