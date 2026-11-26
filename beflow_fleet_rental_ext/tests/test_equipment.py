# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase, day
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .test_day_billing import quantities_and_prices


@tagged("post_install", "-at_install")
class TestEquipmentAndOperator(RentalBillingCase):
    """D6 y D7: canastas y operador son líneas que se cobran por las mismas unidades que la renta."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.basket = cls._service("Canasta", 300.0)
        cls.operator_service = cls._service("Servicio de operador", 500.0)
        cls.operator = cls.env["res.partner"].create({"name": "Operador de prueba"})

    @classmethod
    def _service(cls, name, price):
        return cls.env["product.product"].create({
            "name": name, "type": "service", "list_price": price,
            "property_account_income_id": cls.revenue_account.id,
        })

    def _draft_equipped_contract(self, **values):
        return self.new_contract(0, 10, operator_id=self.operator.id, contract_line_ids=[
            Command.create({"product_id": self.basket.id}),
            Command.create({"product_id": self.operator_service.id}),
        ], **values)

    def _equipped_contract(self, **values):
        contract = self._draft_equipped_contract(**values)
        contract.action_confirm()
        contract.action_run()
        return contract

    def test_equipment_and_operator_are_billed_per_rented_day(self):
        contract = self._equipped_contract()
        contract.action_invoice_create()
        invoice = contract.first_payment_inv
        self.assertEqual(quantities_and_prices(invoice), [(11.0, 1400.0), (11.0, 300.0), (11.0, 500.0)])
        basket_line = invoice.invoice_line_ids[1]
        self.assertEqual(basket_line.product_id, self.basket)
        self.assertIn("Canasta", basket_line.name)
        self.assertIn("TEST-001", basket_line.name)

    def test_each_period_bills_the_equipment(self):
        contract = self._equipped_contract(cost_frequency="weekly")
        contract._run_rental_schedule(day(0))
        self.assertEqual(
            quantities_and_prices(self.rental_invoices(contract)), [(7.0, 1400.0), (7.0, 300.0), (7.0, 500.0)])

    def test_equipment_price_comes_from_the_product_and_can_be_changed_before_starting(self):
        contract = self._draft_equipped_contract()
        self.assertEqual(contract.contract_line_ids.mapped("price_unit"), [300.0, 500.0])
        contract.contract_line_ids[0].price_unit = 250.0
        contract.action_confirm()
        contract.action_run()
        contract.action_invoice_create()
        self.assertEqual(contract.first_payment_inv.invoice_line_ids[1].price_unit, 250.0)

    def test_equipment_is_fixed_once_the_rental_starts(self):
        contract = self._equipped_contract()
        line = contract.contract_line_ids[:1]
        changes = {
            "add": lambda: contract.write({"contract_line_ids": [Command.create({"product_id": self.basket.id})]}),
            "edit": lambda: line.write({"price_unit": 1.0}),
            "remove": line.unlink,
        }
        for name, change in changes.items():
            with self.subTest(change=name), self.assertRaisesRegex(UserError, "before the rental starts"):
                change()

    def test_negative_equipment_rate_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "negative"):
            self.new_contract(0, 10, contract_line_ids=[Command.create({"product_id": self.basket.id, "price_unit": -5.0})])

    def test_rental_users_manage_equipment_and_other_users_cannot_see_it(self):
        contract = self._draft_equipped_contract()
        company = {"company_id": self.env.company.id}
        rental_user = new_test_user(
            self.env, login="rental_equipment", groups="base.group_user,fleet_rental.fleet_rental_group_user", **company)
        plain_user = new_test_user(self.env, login="plain_equipment", groups="base.group_user", **company)
        contract.with_user(rental_user).contract_line_ids = [Command.create({"product_id": self.basket.id})]
        contract.contract_line_ids[:1].with_user(rental_user).unlink()
        self.assertEqual(len(contract.contract_line_ids), 2)
        with self.assertRaises(AccessError):
            contract.contract_line_ids.with_user(plain_user).read(["price_unit"])
