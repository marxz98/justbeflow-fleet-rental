# -*- coding: utf-8 -*-
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestContractGuards(RentalBillingCase):
    """Auditoría 4.8 (M1, M2, L3): las condiciones de la renta no cambian por RPC una vez en marcha."""

    def test_confirming_without_rate_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "rate"):
            self.confirmed_contract(0, 10, cost=0.0)

    def test_negative_amounts_are_refused(self):
        for values in ({"cost": -1.0}, {"first_payment": -1.0}, {"damage_cost": -1.0}):
            with self.subTest(values=values), self.assertRaisesRegex(ValidationError, "negative"):
                self.new_contract(0, 10, **values)

    def test_billing_terms_are_fixed_once_confirmed(self):
        contract = self.running_contract(0, 10)
        for values in ({"rent_by_hour": True}, {"cost_frequency": "weekly"},
                       {"rent_start_date": day(1)}, {"rent_end_date": day(14)}):
            with self.subTest(values=values), self.assertRaisesRegex(UserError, "can no longer be changed"):
                contract.write(values)

    def test_prices_can_be_set_until_the_first_invoice(self):
        contract = self.running_contract(0, 10)
        contract.write({"cost": 1500.0, "first_payment": 100.0})
        contract.action_invoice_create()
        for values in ({"cost": 1600.0}, {"first_payment": 200.0}):
            with self.subTest(values=values), self.assertRaisesRegex(UserError, "can no longer be changed"):
                contract.write(values)
