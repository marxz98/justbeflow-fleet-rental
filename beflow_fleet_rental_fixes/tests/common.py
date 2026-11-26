# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import TransactionCase

BASE_DAY = date(2030, 1, 1)


def day(offset, base=BASE_DAY):
    return base + timedelta(days=offset)


class RentalMixin:
    """Vehículos, cliente y contratos de prueba; se usa con TransactionCase o con la base contable."""

    @classmethod
    def _setup_rental_data(cls):
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Marca de prueba"})
        model = cls.env["fleet.vehicle.model"].create({"name": "Grúa", "brand_id": brand.id})
        cls.vehicle, cls.other_vehicle = cls.env["fleet.vehicle"].create([
            {"model_id": model.id, "license_plate": "TEST-001"},
            {"model_id": model.id, "license_plate": "TEST-002"},
        ])
        cls.customer = cls.env["res.partner"].create({"name": "Cliente de prueba"})

    @classmethod
    def new_contract(cls, start, end, vehicle=None, base=BASE_DAY, **values):
        return cls.env["car.rental.contract"].create({
            "customer_id": cls.customer.id,
            "vehicle_id": (vehicle or cls.vehicle).id,
            "cost": 1400.0,
            "cost_frequency": "no",
            "first_payment": 0.0,
            "rent_start_date": day(start, base),
            "rent_end_date": day(end, base),
            **values,
        })

    @classmethod
    def confirmed_contract(cls, start, end, vehicle=None, **values):
        contract = cls.new_contract(start, end, vehicle, **values)
        contract.action_confirm()
        return contract

    @classmethod
    def running_contract(cls, start, end, vehicle=None, **values):
        contract = cls.confirmed_contract(start, end, vehicle, **values)
        contract.action_run()
        return contract

    @staticmethod
    def start_extension(contract):
        contract.action_run()
        contract.action_extend_rent()


class RentalCase(RentalMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_rental_data()


class RentalBillingCase(RentalMixin, AccountTestInvoicingCommon):
    """Con plan contable, diario de ventas y cuenta de ingresos en la compañía de prueba."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        rental_manager = cls.env.ref("fleet.fleet_group_manager")
        cls.env.user.sudo().group_ids = [Command.link(rental_manager.id)]
        cls._setup_rental_data()
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.revenue_account = cls.company_data["default_account_revenue"]
        cls.service_template = cls.env.ref("fleet_rental.fleet_service_product")
        cls.service_template.property_account_income_id = cls.revenue_account

    def rental_invoices(self, contract):
        return self.env["account.move"].search([("fleet_rent_id", "=", contract.id)], order="id")
