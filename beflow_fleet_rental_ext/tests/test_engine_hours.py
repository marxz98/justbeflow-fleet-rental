# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_day_billing import quantities_and_prices

HOURS = {"rent_by_hour": True, "start_time": "08:00", "end_time": "17:00", "engine_hours_start": 1200.0}


@tagged("post_install", "-at_install")
class TestEngineHours(RentalBillingCase):
    """D5: por horas de motor la renta y el equipo se cobran al cerrar, con horas final − inicial."""

    def _hour_contract(self, **values):
        return self.running_contract(0, 10, **{**HOURS, **values})

    def _check_in(self, contract, final_hours):
        contract.write({"engine_hours_end": final_hours, "state": "checking"})
        contract.action_verify()
        return self.rental_invoices(contract).filtered("is_rental_damage_invoice")

    def test_usage_equipment_and_damage_are_billed_at_check_in(self):
        basket = self.env["product.product"].create({"name": "Canasta", "type": "service", "list_price": 300.0})
        contract = self._hour_contract(
            first_payment=500.0, damage_cost=250.0, contract_line_ids=[Command.create({"product_id": basket.id})])
        contract.action_invoice_create()
        self.assertEqual(quantities_and_prices(contract.first_payment_inv), [(1.0, 500.0)])
        closing = self._check_in(contract, 1208.5)
        self.assertEqual(quantities_and_prices(closing), [(8.5, 1400.0), (8.5, 300.0), (1.0, 250.0)])
        self.assertIn("engine hours", closing.invoice_line_ids[0].name)

    def test_hour_contract_without_fee_has_no_first_invoice(self):
        contract = self._hour_contract()
        contract.action_invoice_create()
        self.assertTrue(contract.first_invoice_created)
        self.assertFalse(self.rental_invoices(contract))

    def test_check_in_without_final_reading_is_refused(self):
        contract = self._hour_contract()
        contract.state = "checking"
        with self.assertRaisesRegex(UserError, "engine hours"):
            contract.action_verify()

    def test_check_in_without_initial_reading_is_refused(self):
        contract = self._hour_contract(engine_hours_start=0.0)
        with self.assertRaisesRegex(UserError, "initial and final engine hours"):
            self._check_in(contract, 1208.5)

    def test_zero_engine_hours_can_be_checked_in(self):
        contract = self._hour_contract()
        self._check_in(contract, 1200.0)
        self.assertEqual(contract.state, "invoice")

    def test_negative_or_decreasing_readings_are_refused(self):
        contract = self._hour_contract()
        for values in ({"engine_hours_start": -1.0}, {"engine_hours_end": 1100.0}):
            with self.subTest(values=values), self.assertRaisesRegex(ValidationError, "Engine hours"):
                contract.write(values)

    def test_engine_hours_cannot_be_recurring(self):
        with self.assertRaisesRegex(ValidationError, "recurring"):
            self.new_contract(0, 10, cost_frequency="weekly", **HOURS)

    def test_extension_is_billed_at_check_in(self):
        contract = self._hour_contract()
        contract.action_invoice_create()
        contract.action_extend_rent()
        contract.rent_end_date = day(14)
        contract.action_confirm_extend_rent()
        self.assertFalse(self.rental_invoices(contract))
