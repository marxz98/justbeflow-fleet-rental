# -*- coding: utf-8 -*-
from datetime import date

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import format_date

from .common import RentalBillingCase, day


@tagged("post_install", "-at_install")
class TestRentalProductAndJournal(RentalBillingCase):
    """4.9 y 4.10: producto de Ajustes, variante correcta y diario de ventas de la compañía."""

    def test_new_contract_defaults_to_company_sale_journal(self):
        contract = self.new_contract(0, 4)
        self.assertEqual(contract.journal_type, self.sale_journal)
        self.assertEqual(contract.account_type, self.sale_journal.default_account_id)

    def test_non_sale_journal_is_rejected_on_confirm(self):
        contract = self.new_contract(0, 4, journal_type=self.company_data["default_journal_purchase"].id)
        with self.assertRaises(UserError):
            contract.action_confirm()

    def test_invoice_uses_product_from_settings(self):
        other = self.env["product.template"].create({
            "name": "Renta de grúa", "type": "service", "property_account_income_id": self.revenue_account.id,
        })
        self.env["ir.config_parameter"].set_param("fleet_rental.fleet_service_product_id", other.id)
        contract = self.running_contract(0, 4, first_payment=500.0)
        contract.action_invoice_create()
        line = contract.first_payment_inv.invoice_line_ids
        self.assertEqual(line.product_id, other.product_variant_id)

    def test_invoice_uses_variant_of_module_product(self):
        contract = self.running_contract(0, 4, first_payment=500.0)
        contract.action_invoice_create()
        line = contract.first_payment_inv.invoice_line_ids
        self.assertEqual(line.product_id.product_tmpl_id, self.service_template)
        self.assertEqual(line.account_id, self.revenue_account)


@tagged("post_install", "-at_install")
class TestFirstInvoice(RentalBillingCase):
    """2.2: factura inicial propia, con vehículo, placa y periodo."""

    def test_first_invoice_is_a_draft_on_sale_journal(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract.action_invoice_create()
        invoice = contract.first_payment_inv
        self.assertTrue(contract.first_invoice_created)
        self.assertTrue(invoice.is_first_invoice)
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.journal_id, self.sale_journal)
        self.assertEqual(invoice.amount_untaxed, 500.0)

    def test_first_invoice_line_names_plate_and_period(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract.action_invoice_create()
        label = contract.first_payment_inv.invoice_line_ids.name
        self.assertIn("TEST-001", label)
        self.assertIn(format_date(self.env, day(0)), label)
        self.assertIn(format_date(self.env, day(10)), label)


@tagged("post_install", "-at_install")
class TestReturnAndDamage(RentalBillingCase):
    """4.3 y 4.7: cerrar no cambia la fecha contratada y el cargo por daños va detallado."""

    def _returned(self, **values):
        contract = self.running_contract(0, 10, **values)
        contract.state = "checking"
        contract.action_verify()
        return contract

    def test_verify_keeps_contracted_end_and_records_return(self):
        contract = self._returned()
        self.assertEqual(contract.rent_end_date, day(10))
        self.assertEqual(contract.actual_return_date, fields.Date.context_today(contract))
        self.assertEqual(contract.state, "invoice")
        self.assertFalse(contract.reserved_fleet_id)

    def test_damage_invoice_has_one_line_per_charge(self):
        tool = self.env["car.tools"].create({"name": "Gato hidráulico", "price": 800.0})
        contract = self._returned(
            damage_cost=4500.0,
            checklist_line=[(0, 0, {"name": tool.id, "price": 800.0, "checklist_active": False})],
        )
        invoice = self.rental_invoices(contract)
        self.assertTrue(invoice.is_rental_damage_invoice)
        lines = invoice.invoice_line_ids.sorted("price_unit")
        self.assertEqual(lines.mapped("price_unit"), [800.0, 4500.0])
        self.assertIn("Gato hidráulico", lines[0].name)
        self.assertIn("TEST-001", lines[1].name)

    def test_verify_without_charges_creates_no_invoice(self):
        contract = self._returned()
        self.assertFalse(self.rental_invoices(contract))

    def test_state_changes_do_not_touch_end_date(self):
        contract = self.running_contract(0, 10)
        contract.state = "invoice"
        self.assertEqual(contract.rent_end_date, day(10))


@tagged("post_install", "-at_install")
class TestRecurringBilling(RentalBillingCase):
    """4.13 a 4.16 y D3: borradores recurrentes idempotentes, sin correo, y vencidos a checking."""

    def _recurring_lines(self, contract):
        return self.env["fleet.rental.line"].search([("rental_number", "=", contract.id)])

    def _billed_dates(self, contract):
        return sorted(self._recurring_lines(contract).mapped("date_today"))

    def test_schedule_twice_same_day_bills_each_period_once(self):
        contract = self.running_contract(0, 30, cost_frequency="daily", cost_generated=1400.0)
        contract._run_rental_schedule(day(3))
        contract._run_rental_schedule(day(3))
        invoices = self.rental_invoices(contract)
        self.assertEqual(self._billed_dates(contract), [day(0), day(1), day(2), day(3)])
        self.assertEqual(len(invoices), 4)
        self.assertEqual(set(invoices.mapped("state")), {"draft"})
        self.assertEqual(invoices.mapped("amount_untaxed"), [1400.0] * 4)

    def test_schedule_catches_up_missed_periods(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly", cost_generated=5000.0)
        contract._run_rental_schedule(day(3))
        self.assertEqual(self._billed_dates(contract), [day(0)])
        contract._run_rental_schedule(day(15))
        self.assertEqual(self._billed_dates(contract), [day(0), day(7), day(14)])

    def test_cancelled_recurring_invoice_is_billed_again(self):
        contract = self.running_contract(0, 30, cost_frequency="weekly", cost_generated=5000.0)
        contract._run_rental_schedule(day(0))
        self.rental_invoices(contract).button_cancel()
        contract._run_rental_schedule(day(1))
        invoices = self.rental_invoices(contract)
        self.assertEqual(invoices.mapped("state"), ["cancel", "draft"])

    def test_monthly_period_labels_follow_the_schedule(self):
        start = date(2030, 1, 31)
        contract = self.running_contract(0, 90, base=start, cost_frequency="monthly", cost_generated=30000.0)
        contract._run_rental_schedule(date(2030, 3, 31))
        self.assertEqual(self._billed_dates(contract), [date(2030, 1, 31), date(2030, 2, 28), date(2030, 3, 31)])
        february = self.rental_invoices(contract)[1].invoice_line_ids
        self.assertIn(format_date(self.env, date(2030, 2, 28)), february.name)
        self.assertIn(format_date(self.env, date(2030, 3, 30)), february.name)

    def test_expired_running_contract_goes_to_checking(self):
        contract = self.running_contract(0, 4)
        contract._run_rental_schedule(day(5))
        self.assertEqual(contract.state, "checking")

    def test_schedule_sends_no_mail(self):
        contract = self.running_contract(0, 30, cost_frequency="daily", cost_generated=1400.0)
        mails_before = self.env["mail.mail"].search_count([])
        contract._run_rental_schedule(day(3))
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)

    def test_broken_contract_does_not_stop_the_others(self):
        broken = self.running_contract(0, 30, cost_frequency="daily", cost_generated=1.0)
        healthy = self.running_contract(0, 30, vehicle=self.other_vehicle, cost_frequency="daily", cost_generated=1.0)
        broken.journal_type = self.company_data["default_journal_purchase"]
        (broken | healthy)._run_rental_schedule(day(0))
        self.assertFalse(self.rental_invoices(broken))
        self.assertEqual(len(self.rental_invoices(healthy)), 1)
        self.assertIn("not created", broken.message_ids[:1].body)

    def test_cron_entrypoint_bills_running_contracts(self):
        today = fields.Date.context_today(self.env.user)
        contract = self.running_contract(-1, 10, base=today, cost_frequency="daily", cost_generated=1400.0)
        self.env["car.rental.contract"].fleet_scheduler()
        self.assertEqual(self._billed_dates(contract), [day(-1, today), today])

    def test_first_invoice_backfill_and_cron_bill_each_period_once(self):
        today = fields.Date.context_today(self.env.user)
        contract = self.running_contract(-14, 30, base=today, cost_frequency="weekly", cost_generated=5000.0)
        contract.action_invoice_create()
        contract._run_rental_schedule(today)
        self.assertEqual(self._billed_dates(contract), [day(-14, today), day(-7, today), today])
        self.assertEqual(len(self.rental_invoices(contract)), 4)


@tagged("post_install", "-at_install")
class TestActionGuards(RentalBillingCase):
    """Las acciones se validan en el servidor, no solo con la visibilidad de los botones."""

    def test_first_invoice_cannot_be_created_twice(self):
        contract = self.running_contract(0, 10, first_payment=500.0)
        contract.action_invoice_create()
        with self.assertRaises(UserError):
            contract.action_invoice_create()

    def test_verify_requires_checking(self):
        contract = self.running_contract(0, 10, damage_cost=300.0)
        with self.assertRaises(UserError):
            contract.action_verify()

    def test_done_requires_invoice_state(self):
        contract = self.running_contract(0, 10)
        with self.assertRaises(UserError):
            contract.set_to_done()

    def test_force_checking_requires_running_with_first_invoice(self):
        contract = self.confirmed_contract(0, 10)
        with self.assertRaises(UserError):
            contract.force_checking()

    def test_confirm_extend_requires_extension_in_progress(self):
        contract = self.running_contract(0, 10)
        with self.assertRaises(UserError):
            contract.action_confirm_extend_rent()


@tagged("post_install", "-at_install")
class TestClosingStates(RentalBillingCase):
    """4.8, 4.18 y 4.19a: cierre en lote, facturas canceladas y cancelación de facturas."""

    def _invoiced_contract(self, vehicle=None):
        contract = self.running_contract(0, 10, vehicle=vehicle, first_payment=500.0)
        contract.action_invoice_create()
        return contract

    def test_draft_invoice_blocks_done(self):
        contract = self._invoiced_contract()
        contract.state = "invoice"
        with self.assertRaises(UserError):
            contract.set_to_done()

    def test_cancelled_invoice_does_not_block_done(self):
        contract = self._invoiced_contract()
        contract.first_payment_inv.button_cancel()
        contract.state = "invoice"
        contract.set_to_done()
        self.assertEqual(contract.state, "done")

    def test_batch_checking_and_done(self):
        contracts = self.running_contract(0, 10) | self.running_contract(0, 10, vehicle=self.other_vehicle)
        contracts.first_invoice_created = True
        contracts.force_checking()
        self.assertEqual(set(contracts.mapped("state")), {"checking"})
        contracts.state = "invoice"
        contracts.set_to_done()
        self.assertEqual(set(contracts.mapped("state")), {"done"})
        self.assertEqual(contracts.mapped("invoice_count"), [0, 0])

    def test_cancelling_invoice_of_done_contract_keeps_done(self):
        contract = self._invoiced_contract()
        contract.state = "done"
        contract.first_payment_inv.button_cancel()
        self.assertEqual(contract.state, "done")

    def test_cancelling_first_invoice_of_running_contract_allows_a_new_one(self):
        contract = self._invoiced_contract()
        contract.first_payment_inv.button_cancel()
        self.assertEqual(contract.state, "running")
        self.assertFalse(contract.first_invoice_created)

    def test_cancelling_damage_invoice_returns_to_checking(self):
        contract = self.running_contract(0, 10, damage_cost=300.0)
        contract.state = "checking"
        contract.action_verify()
        self.rental_invoices(contract).button_cancel()
        self.assertEqual(contract.state, "checking")

    def test_cancelling_other_invoice_keeps_invoice_state(self):
        contract = self._invoiced_contract()
        contract.write({"state": "checking", "damage_cost": 300.0})
        contract.action_verify()
        contract.first_payment_inv.button_cancel()
        self.assertEqual(contract.state, "invoice")

    def test_batch_cancel_across_contracts(self):
        first = self._invoiced_contract()
        second = self._invoiced_contract(vehicle=self.other_vehicle)
        (first.first_payment_inv | second.first_payment_inv).button_cancel()
        self.assertFalse(first.first_invoice_created)
        self.assertFalse(second.first_invoice_created)
