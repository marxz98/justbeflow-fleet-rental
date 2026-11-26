# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import RentalCase, day


@tagged("post_install", "-at_install")
class TestReservationLink(RentalCase):
    """4.4: la reserva conoce su contrato y no sobrevive a él ni al vehículo."""

    def test_confirm_links_reservation_to_contract(self):
        contract = self.confirmed_contract(0, 4)
        self.assertEqual(contract.reserved_fleet_id.contract_id, contract)

    def test_deleting_contract_deletes_its_reservation(self):
        contract = self.confirmed_contract(0, 4)
        reservation = contract.reserved_fleet_id
        contract.unlink()
        self.assertFalse(reservation.exists())

    def test_deleting_vehicle_deletes_its_reservations(self):
        vehicle = self.other_vehicle.copy({"license_plate": "TEST-BORRAR"})
        reservation = self.env["rental.fleet.reserved"].create({
            "reserved_obj_id": vehicle.id, "date_from": day(0), "date_to": day(4),
        })
        vehicle.unlink()
        self.assertFalse(reservation.exists())


@tagged("post_install", "-at_install")
class TestAvailability(RentalCase):
    """4.2: el solape se comprueba contra todas las reservas del vehículo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first = cls.confirmed_contract(0, 4)
        cls.second = cls.confirmed_contract(20, 24)

    def test_overlap_with_first_of_two_reservations_is_rejected(self):
        with self.assertRaises(UserError):
            self.confirmed_contract(2, 7)

    def test_sharing_the_last_day_is_an_overlap(self):
        with self.assertRaises(UserError):
            self.confirmed_contract(4, 7)

    def test_contiguous_free_range_is_accepted(self):
        contract = self.confirmed_contract(5, 19)
        self.assertEqual(contract.state, "reserved")

    def test_other_vehicle_is_not_affected(self):
        contract = self.confirmed_contract(0, 4, vehicle=self.other_vehicle)
        self.assertEqual(contract.state, "reserved")


@tagged("post_install", "-at_install")
class TestExtension(RentalCase):
    """4.1 y 4.5: extender mira y escribe solo la reserva del propio contrato."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first = cls.confirmed_contract(0, 4)
        cls.second = cls.confirmed_contract(20, 24)

    def test_third_contract_on_vehicle_with_two_reservations(self):
        contract = self.new_contract(10, 12)
        contract.rent_end_date = day(13)
        self.assertEqual(contract.rent_end_date, day(13))

    def test_extension_must_go_beyond_own_reservation(self):
        self.start_extension(self.first)
        with self.assertRaises(ValidationError):
            self.first.rent_end_date = day(3)

    def test_extension_updates_only_own_reservation(self):
        self.start_extension(self.first)
        self.first.rent_end_date = day(9)
        self.first.action_confirm_extend_rent()
        self.assertEqual(self.first.reserved_fleet_id.date_to, day(9))
        self.assertEqual(self.second.reserved_fleet_id.date_from, day(20))
        self.assertEqual(self.second.reserved_fleet_id.date_to, day(24))
        self.assertFalse(self.first.read_only)

    def test_extension_over_next_reservation_is_rejected(self):
        self.start_extension(self.first)
        self.first.rent_end_date = day(21)
        with self.assertRaises(UserError):
            self.first.action_confirm_extend_rent()
        self.assertEqual(self.first.reserved_fleet_id.date_to, day(4))

    def test_discard_restores_own_reservation_end(self):
        self.start_extension(self.first)
        self.first.rent_end_date = day(9)
        self.first.action_discard_extend()
        self.assertEqual(self.first.rent_end_date, day(4))
        self.assertFalse(self.first.read_only)
