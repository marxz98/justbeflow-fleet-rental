# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL, format_date

HOUR_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
VEHICLE_STATE_BY_CONTRACT_STATE = {
    "running": "fleet_rental.vehicle_state_rent",
    "cancel": "fleet_rental.vehicle_state_active",
    "invoice": "fleet_rental.vehicle_state_active",
}
SETTLED_PAYMENT_STATES = ("paid", "in_payment", "reversed")


class CarRentalContract(models.Model):
    """Integridad de reservas y constraints de car.rental.contract.

    - 4.2 y 4.5: la disponibilidad se comprueba contra todas las reservas del
      vehículo (fleet_rental solo miraba la última) y también al extender.
    - 4.1: extender compara y escribe solo la reserva del propio contrato.
    - 4.18 y 4.12: las constraints recorren `self` y validan el formato HH:MM.
    - 4.9 y 4.3: diario de ventas de la compañía por defecto, y la fecha de fin
      contratada no se pisa al cerrar: la devolución real va aparte.
    """
    _inherit = "car.rental.contract"

    journal_type = fields.Many2one(default=lambda self: self._default_rental_journal())
    account_type = fields.Many2one(default=lambda self: self._default_rental_journal().default_account_id)
    actual_return_date = fields.Date(
        string="Actual Return Date", readonly=True, copy=False, tracking=True,
        help="Day the vehicle was checked in. The contracted end date is kept as agreed.")

    @api.model
    def _default_rental_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "sale"), *self.env["account.journal"]._check_company_domain(self.env.company)], limit=1)

    def _check_vehicle_available(self, exclude=None):
        self.ensure_one()
        # Serializa confirmaciones y extensiones del mismo vehículo. Un UPDATE y no
        # un FOR UPDATE: en REPEATABLE READ solo una escritura hace fallar (y
        # reintentar) a la transacción concurrente que lee una foto anterior.
        self.env.cr.execute(SQL("UPDATE fleet_vehicle SET write_date = write_date WHERE id = %s", self.vehicle_id.id))
        clash = self.env["rental.fleet.reserved"]._overlapping(
            self.vehicle_id, self.rent_start_date, self.rent_end_date, exclude)[:1]
        if clash:
            raise UserError(self.env._(
                "%(vehicle)s is already reserved from %(date_from)s to %(date_to)s.",
                vehicle=self.vehicle_id.display_name,
                date_from=format_date(self.env, clash.date_from),
                date_to=format_date(self.env, clash.date_to),
            ))

    def action_confirm(self):
        for contract in self:
            contract._check_rental_journal()
            contract._check_vehicle_available()
            super(CarRentalContract, contract).action_confirm()
            contract.reserved_fleet_id.contract_id = contract

    def _check_action_allowed(self, allowed):
        """Las acciones se validan en el servidor: los botones ocultos no protegen de una llamada RPC."""
        blocked = self.filtered(lambda contract: not allowed(contract))
        if blocked:
            raise UserError(self.env._(
                "This action is not available for %s in its current state.",
                ", ".join(contract.display_name or f"#{contract.id}" for contract in blocked)))

    def action_confirm_extend_rent(self):
        self._check_action_allowed(lambda contract: contract.state == "running" and contract.read_only)
        for contract in self:
            contract._check_vehicle_available(exclude=contract.reserved_fleet_id)
            contract.reserved_fleet_id.date_to = contract.rent_end_date
            contract.read_only = False

    def action_discard_extend(self):
        for contract in self:
            values = {"read_only": False}
            if contract.reserved_fleet_id:
                values["rent_end_date"] = contract.reserved_fleet_id.date_to
            contract.write(values)

    @api.constrains("rent_end_date")
    def validate_on_read_only(self):
        for contract in self.filtered("read_only"):
            reserved_to = contract.reserved_fleet_id.date_to
            if reserved_to and contract.rent_end_date <= reserved_to:
                raise ValidationError(self.env._(
                    "Choose an end date later than %s.", format_date(self.env, reserved_to)))

    @api.constrains("rent_start_date", "rent_end_date")
    def validate_dates(self):
        for contract in self:
            if contract.rent_end_date < contract.rent_start_date:
                raise ValidationError(self.env._("The end date cannot be earlier than the start date."))

    @api.constrains("start_time", "end_time", "rent_start_date", "rent_end_date", "rent_by_hour")
    def validate_time(self):
        for contract in self.filtered("rent_by_hour"):
            contract._check_hour_format()
            same_day = contract.rent_end_date == contract.rent_start_date
            if same_day and contract.end_time <= contract.start_time:
                raise ValidationError(self.env._("The end time must be later than the start time."))

    def _check_hour_format(self):
        for value in (self.start_time, self.end_time):
            if not HOUR_PATTERN.match(value or ""):
                raise ValidationError(self.env._("Enter the start and end times as HH:MM, for example 08:30."))

    @api.constrains("checklist_line", "damage_cost")
    def total_updater(self):
        for contract in self:
            lines = contract.checklist_line
            missing = sum(lines.filtered(lambda line: not line.checklist_active).mapped("price"))
            contract.total = sum(lines.mapped("price"))
            contract.tools_missing_cost = missing
            contract.damage_cost_sub = contract.damage_cost
            contract.total_cost = missing + contract.damage_cost

    @api.constrains("state")
    def state_changer(self):
        for contract in self:
            xmlid = VEHICLE_STATE_BY_CONTRACT_STATE.get(contract.state)
            if xmlid:
                contract.vehicle_id.state_id = self.env.ref(xmlid)

    def _invoice_count(self):
        for contract in self:
            contract.invoice_count = self.env["account.move"].search_count([("fleet_rent_id", "=", contract.id)])

    def _check_invoices_settled(self):
        pending = self.env["account.move"].search_count([
            ("fleet_rent_id", "in", self.ids),
            ("state", "!=", "cancel"),
            ("payment_state", "not in", SETTLED_PAYMENT_STATES),
        ], limit=1)
        if pending:
            raise UserError(self.env._("Some invoices of these rentals are still pending payment."))

    def set_to_done(self):
        self._check_action_allowed(lambda contract: contract.state == "invoice")
        self._check_invoices_settled()
        self.write({"state": "done"})

    def force_checking(self):
        self._check_action_allowed(lambda contract: contract.state == "running" and contract.first_invoice_created)
        self._check_invoices_settled()
        self.write({"state": "checking"})
