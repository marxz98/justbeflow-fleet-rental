# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import RentalBillingCase

GUARD = "Only rental billing"


@tagged("post_install", "-at_install")
class TestRentalBillingGuard(RentalBillingCase):
    """Solo la facturación de rentas liga facturas a contratos (5.5, M1): a mano se ocultarían cobros."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.billing_user = new_test_user(
            cls.env, login="billing_guard", groups="base.group_user,account.group_account_invoice",
            company_id=company.id, company_ids=[Command.set(company.ids)])
        cls.contract = cls.running_contract(0, 10, first_payment=500.0)

    def test_an_invoice_cannot_be_linked_to_a_rental_by_hand(self):
        invoice = self.init_invoice("out_invoice", partner=self.customer, amounts=[100.0]).with_user(self.billing_user)
        for values in ({"fleet_rent_id": self.contract.id}, {"is_first_invoice": True}):
            with self.subTest(values=values), self.assertRaisesRegex(UserError, GUARD):
                invoice.write(values)

    def test_a_rental_invoice_cannot_be_unlinked_by_hand(self):
        self.contract.action_invoice_create()
        invoice = self.contract.first_payment_inv.with_user(self.billing_user)
        for values in ({"fleet_rent_id": False}, {"is_first_invoice": False}):
            with self.subTest(values=values), self.assertRaisesRegex(UserError, GUARD):
                invoice.write(values)

    def test_a_rental_invoice_cannot_be_created_by_hand(self):
        Move = self.env["account.move"].with_user(self.billing_user)
        values = {"move_type": "out_invoice", "partner_id": self.customer.id}
        with self.assertRaisesRegex(UserError, GUARD):
            Move.create({**values, "fleet_rent_id": self.contract.id})
        for default in ({"default_fleet_rent_id": self.contract.id}, {"default_is_first_invoice": True}):
            with self.subTest(context=default), self.assertRaisesRegex(UserError, GUARD):
                Move.with_context(**default).create(values)

    def test_copies_and_credit_notes_do_not_count_as_rental_invoices(self):
        self.contract.action_invoice_create()
        invoice = self.contract.first_payment_inv
        invoice.action_post()
        for other in (invoice.copy(), invoice._reverse_moves()):
            with self.subTest(move_type=other.move_type):
                self.assertEqual((other.fleet_rent_id, other.is_first_invoice), (self.env["car.rental.contract"], False))
