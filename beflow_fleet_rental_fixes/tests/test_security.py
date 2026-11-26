# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

RENTAL_GROUPS = {
    "rental_user": "fleet_rental.fleet_rental_group_user",
    "fleet_manager": "fleet.fleet_group_manager",
}


@tagged("post_install", "-at_install")
class TestCronAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cron = cls.env.ref("fleet_rental.cron_scheduler_for_fleet")
        cls.users = {
            login: new_test_user(cls.env, login=login, groups=f"base.group_user,{group}")
            for login, group in RENTAL_GROUPS.items()
        }

    def test_rental_groups_cannot_write_crons(self):
        for login, user in self.users.items():
            with self.subTest(login=login), self.assertRaises(AccessError):
                self.cron.with_user(user).write({"active": False})

    def test_rental_groups_cannot_create_crons(self):
        for login, user in self.users.items():
            with self.subTest(login=login):
                self.assertFalse(self.env["ir.cron"].with_user(user).has_access("create"))

    def test_rental_groups_cannot_trigger_crons(self):
        for login, user in self.users.items():
            with self.subTest(login=login), self.assertRaises(AccessError):
                self.cron.with_user(user).method_direct_trigger()
