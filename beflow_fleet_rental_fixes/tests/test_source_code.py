# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user, tagged

SOURCE_REPOSITORY = "https://github.com/marxz98/justbeflow-fleet-rental"


@tagged("post_install", "-at_install")
class TestSourceCodeLink(TransactionCase):
    """AGPL-3 §13: quien usa las rentas por red debe poder llegar al código que corre."""

    def test_rental_user_sees_a_source_code_link_to_the_public_repository(self):
        user = new_test_user(self.env, login="rental_user", groups="base.group_user,fleet_rental.fleet_rental_group_user")
        menu = self.env.ref("beflow_fleet_rental_fixes.menu_source_code")
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())
        self.assertEqual((menu.action.url, menu.action.target), (SOURCE_REPOSITORY, "new"))

    def test_link_is_translated(self):
        menu = self.env.ref("beflow_fleet_rental_fixes.menu_source_code")
        self.env["res.lang"]._activate_lang("es_GT")
        self.env["ir.module.module"]._load_module_terms(["beflow_fleet_rental_fixes"], ["es_GT"], overwrite=True)
        self.assertEqual(menu.with_context(lang="es_GT").name, "Código fuente")
