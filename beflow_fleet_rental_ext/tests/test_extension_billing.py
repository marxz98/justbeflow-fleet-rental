# -*- coding: utf-8 -*-
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.tests import tagged
from odoo.tools import format_date

from .test_day_billing import quantities_and_prices


@tagged("post_install", "-at_install")
class TestExtensionBilling(RentalBillingCase):
    """D4: los días de una extensión se facturan una sola vez."""

    def _extend(self, contract, new_end):
        contract.action_extend_rent()
        contract.rent_end_date = new_end
        contract.action_confirm_extend_rent()

    def _extra_invoices(self, contract):
        return self.rental_invoices(contract) - contract.first_payment_inv

    def test_extension_after_first_invoice_bills_the_extra_days(self):
        contract = self.running_contract(0, 10)
        contract.action_invoice_create()
        self._extend(contract, day(14))
        extension = self._extra_invoices(contract)
        self.assertEqual(quantities_and_prices(extension), [(4.0, 1400.0)])
        self.assertEqual(extension.state, "draft")
        self.assertIn(format_date(self.env, day(11)), extension.invoice_line_ids.name)
        self.assertIn(format_date(self.env, day(14)), extension.invoice_line_ids.name)

    def test_extension_before_first_invoice_is_billed_in_it(self):
        contract = self.running_contract(0, 10)
        self._extend(contract, day(14))
        self.assertFalse(self.rental_invoices(contract))
        contract.action_invoice_create()
        self.assertEqual(quantities_and_prices(contract.first_payment_inv), [(15.0, 1400.0)])

    def test_extension_of_recurring_contract_is_left_to_its_periods(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly")
        contract.action_invoice_create()
        self._extend(contract, day(40))
        self.assertFalse(self.rental_invoices(contract))
