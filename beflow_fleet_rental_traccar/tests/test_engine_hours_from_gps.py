# -*- coding: utf-8 -*-
from odoo.addons.beflow_fleet_rental_fixes.tests.common import RentalBillingCase
from odoo.exceptions import UserError
from odoo.tests import tagged

HOUR_MS = 3_600_000
HOURS = {"rent_by_hour": True, "start_time": "08:00", "end_time": "17:00"}


@tagged("post_install", "-at_install")
class TestEngineHoursFromGps(RentalBillingCase):
    """6.1 y D5: Traccar publica `hours` en ms; los contratos por horas toman de ahí sus lecturas vacías."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env["traccar.server"].create({
            "name": "Prueba", "url": "http://localhost:8082", "web_url": "http://localhost:8082"})
        cls.device = cls.env["traccar.device"].create({
            "name": "GPS", "server_id": server.id, "remote_id": 7, "vehicle_id": cls.vehicle.id})

    def _report(self, fix_time, hours=None):
        attributes = {} if hours is None else {"hours": hours}
        self.device._apply_position({"id": 1, "fixTime": fix_time, "attributes": attributes})

    def test_hours_attribute_is_stored_in_hours(self):
        self._report("2030-01-01T10:00:00Z", 30_600_000)
        self.assertEqual(self.device.engine_hours, 8.5)

    def test_older_or_hourless_positions_keep_the_reading(self):
        self._report("2030-01-01T10:00:00Z", 10 * HOUR_MS)
        self._report("2030-01-01T09:00:00Z", 8 * HOUR_MS)
        self._report("2030-01-01T11:00:00Z")
        self.assertEqual(self.device.engine_hours, 10.0)

    def test_run_and_verify_take_empty_readings_from_gps(self):
        self._report("2030-01-01T08:00:00Z", 1200 * HOUR_MS)
        contract = self.running_contract(0, 10, **HOURS)
        self.assertEqual(contract.engine_hours_start, 1200.0)
        self._report("2030-01-11T17:00:00Z", int(1208.5 * HOUR_MS))
        contract.state = "checking"
        contract.action_verify()
        self.assertEqual(contract.engine_hours_end, 1208.5)
        self.assertIn("GPS", contract.message_ids[:1].body)

    def test_manual_readings_are_never_overwritten(self):
        self._report("2030-01-01T08:00:00Z", 1200 * HOUR_MS)
        contract = self.running_contract(0, 10, engine_hours_start=1150.0, **HOURS)
        self.assertEqual(contract.engine_hours_start, 1150.0)
        contract.write({"engine_hours_end": 1160.0, "state": "checking"})
        contract.action_verify()
        self.assertEqual(contract.engine_hours_end, 1160.0)

    def test_reading_below_the_initial_one_is_ignored(self):
        self._report("2030-01-01T08:00:00Z", 30 * HOUR_MS)
        contract = self.running_contract(0, 10, engine_hours_start=5000.0, **HOURS)
        contract._fill_engine_hours_from_gps("engine_hours_end")
        self.assertEqual(contract.engine_hours_end, 0.0)
        self.assertFalse(contract.message_ids.filtered(lambda message: "GPS" in (message.body or "")))

    def test_missing_initial_reading_is_not_completed_by_a_later_position(self):
        contract = self.running_contract(0, 10, **HOURS)
        self.assertEqual(contract.engine_hours_start, 0.0)
        self._report("2030-01-11T17:00:00Z", int(1208.5 * HOUR_MS))
        contract.state = "checking"
        with self.assertRaisesRegex(UserError, "initial and final engine hours"):
            contract.action_verify()

    def test_day_contracts_are_left_alone(self):
        self._report("2030-01-01T08:00:00Z", 1200 * HOUR_MS)
        contract = self.running_contract(0, 10)
        self.assertEqual(contract.engine_hours_start, 0.0)
