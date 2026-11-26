# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import RentalCase, day


@tagged("post_install", "-at_install")
class TestContractConstraints(RentalCase):
    """4.18 y 4.12: las constraints aguantan escrituras en lote y horas mal escritas."""

    def test_batch_write_on_two_contracts(self):
        contracts = self.new_contract(0, 4) | self.new_contract(0, 4, vehicle=self.other_vehicle)
        contracts.write({"rent_end_date": day(6), "damage_cost": 10.0})
        self.assertEqual(contracts.mapped("rent_end_date"), [day(6), day(6)])
        self.assertEqual(contracts.mapped("total_cost"), [10.0, 10.0])

    def test_end_before_start_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.new_contract(4, 0)

    def test_malformed_hour_is_a_validation_error(self):
        with self.assertRaises(ValidationError):
            self.new_contract(0, 0, rent_by_hour=True, start_time="8am", end_time="17:00")

    def test_hourly_rent_requires_both_hours(self):
        with self.assertRaises(ValidationError):
            self.new_contract(0, 0, rent_by_hour=True, start_time="08:00")

    def test_same_day_end_must_follow_start(self):
        with self.assertRaises(ValidationError):
            self.new_contract(0, 0, rent_by_hour=True, start_time="17:00", end_time="08:00")

    def test_valid_hourly_rent(self):
        contract = self.new_contract(0, 0, rent_by_hour=True, start_time="08:00", end_time="16:30")
        self.assertTrue(contract.rent_by_hour)
