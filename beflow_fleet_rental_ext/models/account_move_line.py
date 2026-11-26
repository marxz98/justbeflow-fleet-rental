# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    rental_date_from = fields.Date(string="Rented from", readonly=True, copy=False)
    rental_date_to = fields.Date(string="Rented to", readonly=True, copy=False)

    def _onchange_price_unit(self):
        """fleet_rental copiaba aquí el precio de cualquier línea al cargo del contrato (4.19b).

        Con el cargo como línea aparte, editar la factura no debe tocar el contrato.
        """
