# -*- coding: utf-8 -*-
from datetime import date

from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.tests import Form, tagged
from odoo.tools import format_date


def quantities_and_prices(invoice):
    return [(line.quantity, line.price_unit) for line in invoice.invoice_line_ids]


@tagged("post_install", "-at_install")
class TestDayBilling(RentalBillingCase):
    """4.6 y D4: la renta es días × tarifa y el cargo de contrato va aparte."""

    def test_day_contract_bills_days_times_rate(self):
        contract = self.running_contract(0, 10)
        contract.action_invoice_create()
        invoice = contract.first_payment_inv
        self.assertEqual(quantities_and_prices(invoice), [(11.0, 1400.0)])
        self.assertIn("TEST-001", invoice.invoice_line_ids.name)
        self.assertIn(format_date(self.env, day(10)), invoice.invoice_line_ids.name)

    def test_contract_fee_is_a_separate_line(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract.action_invoice_create()
        self.assertEqual(quantities_and_prices(contract.first_payment_inv), [(11.0, 1400.0), (1.0, 500.0)])

    def test_editing_an_invoice_price_keeps_the_contract_fee(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract.action_invoice_create()
        with Form(contract.first_payment_inv) as invoice, invoice.invoice_line_ids.edit(0) as line:
            line.price_unit = 999.0
        self.assertEqual(contract.first_payment, 500.0)


@tagged("post_install", "-at_install")
class TestRecurringDayBilling(RentalBillingCase):
    """D4: con cobro recurrente la renta va en cada periodo y la factura inicial solo lleva el cargo."""

    def _recurring_invoices(self, contract):
        return self.rental_invoices(contract).filtered(lambda move: not move.is_first_invoice)

    def test_first_invoice_of_recurring_contract_has_only_the_fee(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly", first_payment=500.0)
        contract.action_invoice_create()
        self.assertEqual(quantities_and_prices(contract.first_payment_inv), [(1.0, 500.0)])

    def test_recurring_contract_without_fee_has_no_first_invoice(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly")
        contract.action_invoice_create()
        self.assertTrue(contract.first_invoice_created)
        self.assertFalse(self.rental_invoices(contract))

    def test_each_period_bills_its_days(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly")
        contract._run_rental_schedule(day(28))
        invoices = self._recurring_invoices(contract)
        self.assertEqual([quantities_and_prices(move) for move in invoices], [[(7.0, 1400.0)]] * 4 + [[(3.0, 1400.0)]])
        self.assertEqual(contract.recurring_line.sorted("date_today").mapped("recurring_amount")[:2], [9800.0, 9800.0])

    def test_february_bills_28_days(self):
        contract = self.running_contract(0, 59, base=date(2030, 2, 1), cost_frequency="monthly")
        contract._run_rental_schedule(date(2030, 2, 1))
        self.assertEqual(quantities_and_prices(self._recurring_invoices(contract)), [(28.0, 1400.0)])
