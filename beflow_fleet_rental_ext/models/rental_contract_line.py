# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RentalContractLine(models.Model):
    """Una unidad de equipo o servicio (canasta, operador) que se cobra por las mismas unidades que la renta."""
    _name = "beflow.rental.contract.line"
    _description = "Rental equipment line"
    _order = "contract_id, id"

    contract_id = fields.Many2one("car.rental.contract", string="Contract", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one(
        "product.product", string="Equipment or service", required=True, domain=[("sale_ok", "=", True)])
    price_unit = fields.Float(
        string="Rate", digits="Product Price", compute="_compute_price_unit", store=True, readonly=False, precompute=True)

    @api.depends("product_id")
    def _compute_price_unit(self):
        for line in self:
            line.price_unit = line.product_id.lst_price

    @api.constrains("price_unit")
    def _check_price_unit(self):
        if any(line.price_unit < 0 for line in self):
            raise ValidationError(self.env._("The rate of an equipment line cannot be negative."))

    # Auditoría 4.8 (M3): el equipo forma parte de lo pactado; la vista ya lo bloquea, aquí también por RPC.

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_contract_not_started()
        return lines

    def write(self, vals):
        self._check_contract_not_started()
        result = super().write(vals)
        self._check_contract_not_started()
        return result

    def unlink(self):
        self._check_contract_not_started()
        return super().unlink()

    def _check_contract_not_started(self):
        started = self.contract_id.filtered(lambda contract: contract.state not in ("draft", "reserved"))
        if started:
            raise UserError(self.env._(
                "Equipment can only be changed before the rental starts (%s).",
                ", ".join(contract.display_name or f"#{contract.id}" for contract in started)))

    def _prepare_invoice_line_vals(self, period_label, quantity):
        return {
            "product_id": self.product_id.id,
            "name": self.env._("%(item)s for %(period)s", item=self.product_id.display_name, period=period_label),
            "quantity": quantity,
            "price_unit": self.price_unit,
        }
