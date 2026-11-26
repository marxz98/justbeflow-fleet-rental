# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from .account_move import rental_billing

_logger = logging.getLogger(__name__)

BILLING_STEP = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "monthly": relativedelta(months=1),
    "yearly": relativedelta(years=1),
}
ONE_DAY = relativedelta(days=1)


class CarRentalContract(models.Model):
    """Ruta de facturación propia de car.rental.contract.

    fleet_rental arma cada factura en línea, con el producto equivocado
    (4.10), el diario id=1 (4.9) y sin puntos de extensión. Aquí se reescriben
    action_invoice_create, action_verify, fleet_scheduler y fleet_scheduler1
    sin super() sobre funciones pequeñas que beflow_fleet_rental_ext amplía.
    El cron solo deja borradores, nunca publica ni envía correo (D3).
    """
    _inherit = "car.rental.contract"

    # --- Producto, diario y valores de factura ---

    def _rental_product(self):
        param = self.env["ir.config_parameter"].sudo().get_param("fleet_rental.fleet_service_product_id")
        template = self.env["product.template"].browse(int(param or 0)).exists()
        return (template or self.env.ref("fleet_rental.fleet_service_product")).product_variant_id

    def _check_rental_journal(self):
        for contract in self:
            journal = contract.journal_type
            if journal.type != "sale" or journal.company_id != contract.company_id:
                raise UserError(self.env._(
                    "Contract %s needs a sales journal of its own company.", contract.display_name))

    def _rental_period_label(self, date_from, date_to):
        return self.env._(
            "%(vehicle)s, from %(date_from)s to %(date_to)s",
            vehicle=self.vehicle_id.display_name,
            date_from=format_date(self.env, date_from),
            date_to=format_date(self.env, date_to),
        )

    def _prepare_rental_invoice_vals(self, line_vals, **extra):
        self._check_rental_journal()
        return {
            "move_type": "out_invoice",
            "partner_id": self.customer_id.id,
            "journal_id": self.journal_type.id,
            "company_id": self.company_id.id,
            "invoice_origin": self.name,
            "fleet_rent_id": self.id,
            "invoice_date_due": self.rent_end_date,
            "invoice_line_ids": [Command.create(vals) for vals in line_vals],
            **extra,
        }

    def _create_rental_invoice(self, line_vals, **extra):
        with rental_billing():
            return self.env["account.move"].create(self._prepare_rental_invoice_vals(line_vals, **extra))

    def _prepare_first_invoice_line_vals(self):
        return [{
            "product_id": self._rental_product().id,
            "name": self._rental_period_label(self.rent_start_date, self.rent_end_date),
            "quantity": 1.0,
            "price_unit": self.first_payment,
        }]

    # --- Factura inicial (2.2) ---

    def action_invoice_create(self):
        self._check_action_allowed(lambda c: c.state == "running" and not c.first_invoice_created and not c.read_only)
        invoices = self.env["account.move"]
        for contract in self:
            contract._create_recurring_invoices_until(fields.Date.context_today(contract))
            invoices |= contract._create_first_invoice()
        return invoices._get_records_action(name=self.env._("Rental invoices"))

    def _create_first_invoice(self):
        """Sin líneas (recurrente sin cargo) no hay factura, pero el contrato queda como facturado."""
        line_vals = self._prepare_first_invoice_line_vals()
        invoice = self.env["account.move"]
        if line_vals:
            invoice = self._create_rental_invoice(line_vals, is_first_invoice=True)
        self.write({"first_invoice_created": True, "first_payment_inv": invoice.id})
        return invoice

    # --- Devolución y daños (4.3, 4.7) ---

    def action_verify(self):
        self._check_action_allowed(lambda contract: contract.state == "checking")
        for contract in self:
            contract.write({"state": "invoice", "actual_return_date": fields.Date.context_today(contract)})
            # La reserva es del contrato y se libera al devolver: el usuario de rentas no borra reservas.
            contract.reserved_fleet_id.sudo().unlink()
            contract.vehicle_id.rental_check_availability = True
            damage_lines = contract._prepare_damage_line_vals()
            if damage_lines:
                contract._create_rental_invoice(damage_lines, is_rental_damage_invoice=True)
        return {"type": "ir.actions.act_window_close"}

    def _prepare_damage_line_vals(self):
        product = self._rental_product()
        missing = self.checklist_line.filtered(lambda line: not line.checklist_active and line.price)
        lines = [{
            "product_id": product.id,
            "name": self.env._("Missing accessory: %s", line.name.name),
            "quantity": 1.0,
            "price_unit": line.price,
        } for line in missing]
        if self.damage_cost:
            lines.append({
                "product_id": product.id,
                "name": self.env._("Damage: %s", self._rental_period_label(self.rent_start_date, self.rent_end_date)),
                "quantity": 1.0,
                "price_unit": self.damage_cost,
            })
        return lines

    # --- Cobro recurrente (4.13 a 4.16, D3) ---

    def _billing_periods(self, until):
        """Periodos (inicio, fin) que empiezan hasta `until`, anclados a la fecha de inicio.

        Cada inicio es inicio + n pasos, no el anterior + 1 paso: un contrato
        mensual del 31 de enero cobra el 28 de febrero y vuelve al 31 de marzo.
        """
        step = BILLING_STEP.get(self.cost_frequency)
        periods, index = [], 0
        while step and self.rent_start_date + step * index <= min(until, self.rent_end_date):
            next_start = self.rent_start_date + step * (index + 1)
            periods.append((self.rent_start_date + step * index, min(next_start - ONE_DAY, self.rent_end_date)))
            index += 1
        return periods

    def _has_recurring_line(self, billing_date):
        """Un periodo cuenta como cobrado solo si su factura sigue viva (no borrada ni cancelada)."""
        return bool(self.env["fleet.rental.line"].search_count([
            ("rental_number", "=", self.id),
            ("date_today", "=", billing_date),
            ("invoice_ref", "!=", False),
            ("invoice_ref.state", "!=", "cancel"),
        ], limit=1))

    def _prepare_recurring_line_vals(self, date_from, date_to):
        """Lista vacía si el periodo ya está cobrado."""
        if self._has_recurring_line(date_from):
            return []
        return [{
            "product_id": self._rental_product().id,
            "name": self._rental_period_label(date_from, date_to),
            "quantity": 1.0,
            "price_unit": self.cost_generated,
        }]

    def _create_recurring_invoice(self, date_from, date_to):
        line_vals = self._prepare_recurring_line_vals(date_from, date_to)
        if not line_vals:
            return
        invoice = self._create_rental_invoice(line_vals)
        self.env["fleet.rental.line"].create({
            "name": self.vehicle_id.name,
            "date_today": date_from,
            "account_info": invoice.invoice_line_ids[:1].account_id.display_name,
            "rental_number": self.id,
            "recurring_amount": sum(vals["quantity"] * vals["price_unit"] for vals in line_vals),
            "invoice_number": invoice.id,
            "invoice_ref": invoice.id,
        })

    def _create_recurring_invoices_until(self, until):
        for date_from, date_to in self._billing_periods(until):
            self._create_recurring_invoice(date_from, date_to)

    def fleet_scheduler1(self, rent_date):
        for contract in self:
            for date_from, date_to in contract._billing_periods(rent_date):
                if date_from == rent_date:
                    contract._create_recurring_invoice(date_from, date_to)

    @api.private
    @api.model
    def fleet_scheduler(self):
        self.search([("state", "=", "running")])._run_rental_schedule(fields.Date.context_today(self))

    def _run_rental_schedule(self, today):
        """Pasa a checking lo vencido y cobra los periodos pendientes, también los de días sin cron."""
        running = self.filtered(lambda contract: contract.state == "running")
        expired = running.filtered(lambda contract: contract.rent_end_date < today)
        expired.write({"state": "checking"})
        for contract in running - expired:
            contract._bill_pending_periods_safely(today)

    def _bill_pending_periods_safely(self, today):
        """Un contrato mal configurado no frena el cobro de los demás y deja constancia en su chatter."""
        try:
            with self.env.cr.savepoint():
                self._create_recurring_invoices_until(today)
        except Exception as error:  # noqa: BLE001 - el cron debe seguir con los demás contratos
            _logger.exception("Rental %s: recurring invoices not created", self.display_name)
            self.message_post(body=self.env._("Recurring invoices were not created: %s", error))
