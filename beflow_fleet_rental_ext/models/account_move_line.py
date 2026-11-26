# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.addons.beflow_fleet_rental_fixes.models.account_move import check_rental_billing, fields_set

COVERAGE_FIELDS = ("rental_date_from", "rental_date_to")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    rental_date_from = fields.Date(string="Rented from", readonly=True, copy=False)
    rental_date_to = fields.Date(string="Rented to", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        check_rental_billing(self.env, fields_set(lines, COVERAGE_FIELDS))
        return lines

    def write(self, vals):
        check_rental_billing(self.env, set(COVERAGE_FIELDS) & vals.keys())
        return super().write(vals)

    def _onchange_price_unit(self):
        """fleet_rental copiaba aquí el precio de cualquier línea al cargo del contrato (4.19b).

        Con el cargo como línea aparte, editar la factura no debe tocar el contrato.
        """
