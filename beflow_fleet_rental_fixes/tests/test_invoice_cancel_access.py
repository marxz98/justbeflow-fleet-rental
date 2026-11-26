# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import get_public_method
from odoo.tests import new_test_user, tagged

from .common import RentalBillingCase


@tagged("post_install", "-at_install")
class TestInvoiceCancelAccess(RentalBillingCase):
    """fleet_rental busca el contrato en cada cancelación: facturación necesita leerlo, no editarlo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.billing_user = new_test_user(
            cls.env, login="billing_only", groups="base.group_user,account.group_account_invoice",
            company_id=company.id, company_ids=[Command.set(company.ids)])

    def _posted_invoice(self):
        return self.init_invoice("out_invoice", partner=self.customer, amounts=[100.0], post=True)

    def test_billing_user_cancels_an_invoice_without_rental(self):
        invoice = self._posted_invoice()
        invoice.with_user(self.billing_user).button_cancel()
        self.assertEqual(invoice.state, "cancel")

    def test_several_invoices_without_rental_are_cancelled_together(self):
        invoices = self._posted_invoice() | self._posted_invoice()
        invoices.with_user(self.billing_user).button_cancel()
        self.assertEqual(invoices.mapped("state"), ["cancel", "cancel"])

    def test_billing_user_reads_contracts_but_cannot_change_them(self):
        contract = self.new_contract(0, 10).with_user(self.billing_user)
        self.assertTrue(contract.has_access("read"))
        for operation in ("write", "create", "unlink"):
            with self.subTest(operation=operation):
                self.assertFalse(contract.has_access(operation))

    def test_cancelling_a_rental_invoice_still_needs_the_rental_group(self):
        contract = self.running_contract(0, 10)
        invoice = self._posted_invoice()
        invoice.fleet_rent_id = contract
        with self.assertRaises(AccessError) as denied:
            invoice.with_user(self.billing_user).button_cancel()
        self.assertIn("car.rental.contract", str(denied.exception))
        self.assertEqual((invoice.state, contract.state), ("posted", "running"))

    def test_rental_scheduler_is_not_callable_over_rpc(self):
        contracts = self.env["car.rental.contract"].with_user(self.billing_user)
        with self.assertRaises(AccessError):
            get_public_method(contracts, "fleet_scheduler")
