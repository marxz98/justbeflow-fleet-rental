# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

GUARD = "Only rental billing"


@tagged("post_install", "-at_install")
class TestCoverageGuard(RentalBillingCase):
    """Las fechas de cobertura solo las pone la facturación de rentas (5.5, M1): a mano, días sin cobrar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.billing_user = new_test_user(
            cls.env, login="billing_coverage", groups="base.group_user,account.group_account_invoice",
            company_id=company.id, company_ids=[Command.set(company.ids)])

    def test_coverage_dates_cannot_be_set_by_hand(self):
        contract = self.running_contract(0, 10)
        contract.action_invoice_create()
        line = contract.first_payment_inv.invoice_line_ids[0].with_user(self.billing_user)
        for values in ({"rental_date_to": day(30)}, {"rental_date_from": False}):
            with self.subTest(values=values), self.assertRaisesRegex(UserError, GUARD):
                line.write(values)

    def test_coverage_dates_cannot_be_created_by_hand(self):
        Move = self.env["account.move"].with_user(self.billing_user)
        line = {"name": "x", "quantity": 1, "price_unit": 1.0}
        with self.assertRaisesRegex(UserError, GUARD):
            Move.create({"move_type": "out_invoice", "partner_id": self.customer.id, "invoice_line_ids": [
                Command.create({**line, "rental_date_from": day(0), "rental_date_to": day(30)})]})
        draft = Move.create({"move_type": "out_invoice", "partner_id": self.customer.id})
        with self.assertRaisesRegex(UserError, GUARD):
            self.env["account.move.line"].with_user(self.billing_user).with_context(
                default_rental_date_from=day(0), default_rental_date_to=day(30)).create({**line, "move_id": draft.id})
