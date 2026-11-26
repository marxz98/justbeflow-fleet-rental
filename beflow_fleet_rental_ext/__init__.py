# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    env["car.rental.contract"].search([("first_invoice_created", "=", True)])._mark_legacy_first_invoice_coverage()
