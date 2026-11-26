# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import new_test_user, tagged

from .common import RentalBillingCase


@tagged("post_install", "-at_install")
class TestRentalUserGroups(RentalBillingCase):
    """Quien alquila factura y cobra, pero no lleva la contabilidad (5.5, H3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clerk = cls._user("rental_clerk", "fleet_rental.fleet_rental_group_user")

    @classmethod
    def _user(cls, login, group):
        company = cls.env.company
        return new_test_user(cls.env, login=login, groups=f"base.group_user,{group}",
                             company_id=company.id, company_ids=[Command.set(company.ids)])

    def test_rental_and_fleet_managers_invoice_without_full_accounting(self):
        manager = self._user("fleet_boss", "fleet.fleet_group_manager")
        for user in (self.clerk, manager):
            with self.subTest(login=user.login):
                self.assertTrue(user.has_group("account.group_account_invoice"))
                self.assertFalse(user.has_group("account.group_account_user"))

    def test_rental_user_bills_posts_and_registers_the_payment(self):
        contract = self.running_contract(0, 10, first_payment=500.0).with_user(self.clerk)
        contract.action_invoice_create()
        invoice = contract.first_payment_inv
        invoice.action_post()
        self.env["account.payment.register"].with_user(self.clerk).with_context(
            active_model="account.move", active_ids=invoice.ids).create({})._create_payments()
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

    def test_rental_user_checks_in_with_a_damage_invoice(self):
        contract = self.running_contract(0, 10, damage_cost=300.0)
        contract.first_invoice_created = True
        contract.force_checking()
        contract.with_user(self.clerk).action_verify()
        damage = self.rental_invoices(contract).filtered("is_rental_damage_invoice")
        self.assertIn(300.0, damage.invoice_line_ids.mapped("price_unit"))
