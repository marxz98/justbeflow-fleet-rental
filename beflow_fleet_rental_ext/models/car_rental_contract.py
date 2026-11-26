# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.addons.beflow_fleet_rental_fixes.models.car_rental_billing import ONE_DAY
from odoo.exceptions import UserError, ValidationError


class CarRentalContract(models.Model):
    """Renta como unidades × tarifa, con su equipo, y cargo de contrato aparte (4.6, D4-D7).

    Por días, cada línea de renta guarda los días que cubre y cada factura
    (inicial, recurrente, de extensión o de cierre) cobra solo los días que
    ninguna factura viva cubre: anular una factura los deja pendientes y el
    cierre cobra lo que quede. Por horas de motor, la renta va en el cierre. El
    cargo va en la factura inicial o, si no la hay, en el cierre.
    """
    _inherit = "car.rental.contract"

    cost = fields.Float(string="Rate", help="Price per rented day, or per engine hour.")
    first_payment = fields.Float(
        string="Contract fee",
        help="Charged once, on its own line of the first invoice, besides the rent. Leave 0 for none.")
    operator_id = fields.Many2one("res.partner", string="Operator", tracking=True)
    contract_line_ids = fields.One2many("beflow.rental.contract.line", "contract_id", string="Equipment")
    rent_by_hour = fields.Boolean(
        string="By engine hours",
        help="Rent and equipment are billed at check-in, by final minus initial engine hours.")
    engine_hours_start = fields.Float(string="Initial engine hours", tracking=True)
    engine_hours_end = fields.Float(string="Final engine hours", tracking=True)

    @api.constrains("engine_hours_start", "engine_hours_end")
    def _check_engine_hours(self):
        for contract in self:
            start, end = contract.engine_hours_start, contract.engine_hours_end
            if start < 0 or end < 0 or (end and end < start):
                raise ValidationError(self.env._(
                    "Engine hours cannot be negative, and the final reading cannot be lower than the initial one."))

    @api.constrains("rent_by_hour", "cost_frequency")
    def _check_engine_hours_not_recurring(self):
        if any(contract.rent_by_hour and contract.cost_frequency != "no" for contract in self):
            raise ValidationError(self.env._("A contract billed by engine hours cannot have recurring invoices."))

    @api.constrains("cost", "first_payment", "damage_cost", "state")
    def _check_amounts(self):
        for contract in self:
            if min(contract.cost, contract.first_payment, contract.damage_cost) < 0:
                raise ValidationError(self.env._("Rate, contract fee and damage cost cannot be negative."))
            if contract.cost <= 0 and contract.state not in ("draft", "cancel"):
                raise ValidationError(self.env._(
                    "Set the rate of contract %s before confirming it.", contract.display_name or f"#{contract.id}"))

    # --- Condiciones fijas (auditoría 4.8: M2): la vista ya las bloquea, aquí también por RPC ---

    def write(self, vals):
        for contract in self:
            frozen = contract._frozen_terms() & vals.keys()
            if frozen:
                labels = ", ".join(sorted(contract._fields[name]._description_string(self.env) for name in frozen))
                raise UserError(self.env._(
                    "These terms of %(contract)s can no longer be changed: %(fields)s.",
                    contract=contract.display_name or f"#{contract.id}", fields=labels))
        return super().write(vals)

    def _frozen_terms(self):
        """Modo, frecuencia y fechas al confirmar (salvo extender); tarifa y cargo al facturar o cerrar."""
        frozen = set()
        if self.state != "draft":
            frozen |= {"rent_by_hour", "cost_frequency", "rent_start_date"}
            if not self.read_only:
                frozen.add("rent_end_date")
        if self.first_invoice_created or self.state not in ("draft", "reserved", "running"):
            frozen |= {"cost", "first_payment"}
        return frozen

    # --- Cobertura de días (auditoría 4.8: H1-H3, M4) ---

    def _covered_days(self):
        lines = self.env["account.move.line"].search([
            ("move_id.fleet_rent_id", "=", self.id),
            ("move_id.state", "!=", "cancel"),
            ("rental_date_from", "!=", False),
        ])
        return {line.rental_date_from + timedelta(days=offset)
                for line in lines for offset in range((line.rental_date_to - line.rental_date_from).days + 1)}

    def _uncovered_ranges(self, date_from, date_to):
        covered, ranges, day = self._covered_days(), [], date_from
        while day <= date_to:
            if day not in covered:
                if ranges and ranges[-1][1] == day - ONE_DAY:
                    ranges[-1] = (ranges[-1][0], day)
                else:
                    ranges.append((day, day))
            day += ONE_DAY
        return ranges

    def _fee_billed(self):
        return bool(self.env["account.move"].search_count([
            ("fleet_rent_id", "=", self.id), ("is_first_invoice", "=", True), ("state", "!=", "cancel")], limit=1))

    # --- Líneas de factura ---

    def _prepare_rent_line_vals(self, label, quantity, **coverage):
        rent = {
            "product_id": self._rental_product().id,
            "name": label,
            "quantity": quantity,
            "price_unit": self.cost,
            **coverage,
        }
        return [rent] + [line._prepare_invoice_line_vals(label, quantity) for line in self.contract_line_ids]

    def _prepare_day_line_vals(self, date_from, date_to):
        days = (date_to - date_from).days + 1
        label = self._rental_period_label(date_from, date_to)
        return self._prepare_rent_line_vals(label, days, rental_date_from=date_from, rental_date_to=date_to)

    def _prepare_uncovered_day_line_vals(self, date_from, date_to):
        return [vals for start, end in self._uncovered_ranges(date_from, date_to)
                for vals in self._prepare_day_line_vals(start, end)]

    def _prepare_engine_hours_line_vals(self):
        period = self._rental_period_label(self.rent_start_date, self.rent_end_date)
        hours = self.engine_hours_end - self.engine_hours_start
        return self._prepare_rent_line_vals(self.env._("%s, engine hours", period), hours)

    def _prepare_contract_fee_line_vals(self):
        if self.first_payment <= 0 or self._fee_billed():
            return []
        return [{
            "product_id": self._rental_product().id,
            "name": self.env._("Contract fee: %s", self.vehicle_id.display_name),
            "quantity": 1.0,
            "price_unit": self.first_payment,
        }]

    # --- Ganchos de beflow_fleet_rental_fixes ---

    def _bills_days_upfront(self):
        return not self.rent_by_hour and self.cost_frequency == "no"

    # --- Ganchos de beflow_fleet_rental_fixes ---

    def _prepare_first_invoice_line_vals(self):
        rent = []
        if self._bills_days_upfront():
            rent = self._prepare_uncovered_day_line_vals(self.rent_start_date, self.rent_end_date)
        return rent + self._prepare_contract_fee_line_vals()

    def _prepare_recurring_line_vals(self, date_from, date_to):
        return self._prepare_uncovered_day_line_vals(date_from, date_to)

    def _prepare_damage_line_vals(self):
        """El cierre cobra todo lo pendiente: la renta (por horas, o los días sin factura viva) y el cargo."""
        if self.rent_by_hour:
            rent = self._prepare_engine_hours_line_vals()
        else:
            rent = self._prepare_uncovered_day_line_vals(self.rent_start_date, self.rent_end_date)
        return rent + self._prepare_contract_fee_line_vals() + super()._prepare_damage_line_vals()

    # --- Extensión y cierre ---

    def action_confirm_extend_rent(self):
        """Sin factura inicial aún, ella cubrirá la nueva fecha; con recurrente, sus periodos; por horas, el cierre."""
        super().action_confirm_extend_rent()
        for contract in self.filtered(lambda contract: contract.first_invoice_created and contract._bills_days_upfront()):
            line_vals = contract._prepare_uncovered_day_line_vals(contract.rent_start_date, contract.rent_end_date)
            if line_vals:
                contract._create_rental_invoice(line_vals)

    def _mark_legacy_first_invoice_coverage(self):
        """Al instalar ext, la factura inicial de un contrato por días sin recurrente (1 × total) cubría todo."""
        for contract in self.filtered(lambda contract: contract.cost_frequency == "no"):
            invoice = contract.first_payment_inv
            if invoice and invoice.state != "cancel":
                invoice.invoice_line_ids[:1].write({
                    "rental_date_from": contract.rent_start_date, "rental_date_to": contract.rent_end_date})

    def action_verify(self):
        unread = self.filtered(lambda contract: contract.rent_by_hour and (
            contract.engine_hours_start <= 0 or contract.engine_hours_end < contract.engine_hours_start))
        if unread:
            raise UserError(self.env._(
                "Enter the initial and final engine hours of %s before checking in.",
                ", ".join(contract.display_name or f"#{contract.id}" for contract in unread)))
        return super().action_verify()
