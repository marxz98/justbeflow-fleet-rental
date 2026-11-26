# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.tests import tagged

from .test_day_billing import quantities_and_prices


@tagged("post_install", "-at_install")
class TestBillingCoverage(RentalBillingCase):
    """Auditoría 4.8 (H1-H3, M4): cada día de renta se cobra una sola vez, y el cierre cobra lo pendiente."""

    def _extend(self, contract, new_end):
        contract.action_extend_rent()
        contract.rent_end_date = new_end
        contract.action_confirm_extend_rent()

    def _live_invoices(self, contract):
        return self.rental_invoices(contract).filtered(lambda move: move.state != "cancel")

    def _rent_days(self, contract):
        lines = self._live_invoices(contract).invoice_line_ids
        return sum(lines.filtered(lambda line: line.price_unit == contract.cost).mapped("quantity"))

    def _check_in(self, contract):
        contract.state = "checking"
        contract.action_verify()
        return self.rental_invoices(contract).filtered("is_rental_damage_invoice")

    def test_recreated_first_invoice_skips_days_billed_by_an_extension(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract.action_invoice_create()
        self._extend(contract, day(14))
        contract.first_payment_inv.button_cancel()
        contract.action_invoice_create()
        self.assertEqual(quantities_and_prices(contract.first_payment_inv), [(11.0, 1400.0), (1.0, 500.0)])
        self.assertEqual(self._rent_days(contract), 15)

    def test_contract_expired_without_first_invoice_is_billed_at_check_in(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract._run_rental_schedule(day(11))
        self.assertEqual(contract.state, "checking")
        closing = self._check_in(contract)
        self.assertEqual(quantities_and_prices(closing), [(11.0, 1400.0), (1.0, 500.0)])

    def test_extension_of_recurring_contract_bills_the_rest_of_the_cut_period(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly")
        contract._run_rental_schedule(day(28))
        self._extend(contract, day(40))
        contract._run_rental_schedule(day(40))
        self.assertEqual(self._rent_days(contract), 41)

    def test_cancelled_extension_invoice_is_billed_at_check_in(self):
        contract = self.running_contract(0, 10)
        contract.action_invoice_create()
        self._extend(contract, day(14))
        (self.rental_invoices(contract) - contract.first_payment_inv).button_cancel()
        closing = self._check_in(contract)
        self.assertEqual(quantities_and_prices(closing), [(4.0, 1400.0)])
        self.assertEqual(self._rent_days(contract), 15)

    def test_each_extension_bills_its_own_days_with_equipment(self):
        basket = self.env["product.product"].create({"name": "Canasta", "type": "service", "list_price": 300.0})
        contract = self.running_contract(0, 10, contract_line_ids=[Command.create({"product_id": basket.id})])
        contract.action_invoice_create()
        self._extend(contract, day(14))
        self._extend(contract, day(20))
        extensions = self.rental_invoices(contract) - contract.first_payment_inv
        self.assertEqual([quantities_and_prices(move) for move in extensions],
                         [[(4.0, 1400.0), (4.0, 300.0)], [(6.0, 1400.0), (6.0, 300.0)]])

    def test_check_in_after_full_billing_bills_only_damage(self):
        contract = self.running_contract(0, 10, first_payment=500.0, damage_cost=250.0)
        contract.action_invoice_create()
        closing = self._check_in(contract)
        self.assertEqual(quantities_and_prices(closing), [(1.0, 250.0)])

    def test_first_invoice_from_before_ext_covers_the_whole_contract(self):
        contract = self.running_contract(0, 10, first_payment=15400.0)
        legacy = contract._create_rental_invoice([{
            "product_id": contract._rental_product().id, "name": "Renta", "quantity": 1.0, "price_unit": 15400.0,
        }], is_first_invoice=True)
        contract.write({"first_invoice_created": True, "first_payment_inv": legacy.id})
        contract._mark_legacy_first_invoice_coverage()
        contract.damage_cost = 250.0
        closing = self._check_in(contract)
        self.assertEqual(quantities_and_prices(closing), [(1.0, 250.0)])
