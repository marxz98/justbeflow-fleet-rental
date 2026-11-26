# -*- coding: utf-8 -*-
from ast import literal_eval

from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAvailabilityCalendar(RentalBillingCase):
    """6.4: calendario de los contratos que ocupan un vehículo (los que tienen reserva)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.action = cls.env.ref("beflow_fleet_rental_ext.action_rental_availability")

    def test_calendar_spans_the_contract_dates_by_vehicle(self):
        arch = self.env["car.rental.contract"].get_views([(self.action.view_id.id, "calendar")])["views"]["calendar"]["arch"]
        self.assertIn('date_start="rent_start_date"', arch)
        self.assertIn('date_stop="rent_end_date"', arch)
        self.assertIn('color="vehicle_id"', arch)

    def test_only_contracts_holding_the_vehicle_are_shown(self):
        reserved = self.confirmed_contract(0, 5)
        running = self.running_contract(10, 15)
        draft = self.new_contract(20, 25)
        closed = self.running_contract(30, 35)
        closed.state = "done"
        returning = self.running_contract(40, 45)
        returning.state = "checking"
        shown = self.env["car.rental.contract"].search(literal_eval(self.action.domain))
        self.assertEqual(shown & (reserved | running | draft | closed | returning), reserved | running | returning)
