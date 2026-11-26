# -*- coding: utf-8 -*-
from odoo import fields, models

RESTORED_CONTRACT_FIELDS = ("state", "first_invoice_created")


class AccountMove(models.Model):
    """Cancelar una factura de renta solo deshace lo que esa factura provocó (4.19a).

    fleet_rental pasaba el contrato a `checking` aunque estuviera en `done` y
    fallaba con varias facturas a la vez. Se mantiene la cadena de super()
    (otros módulos también extienden button_cancel), factura a factura, y se
    restaura lo que fleet_rental cambió antes de aplicar la regla correcta:
    - factura inicial de una renta en curso: se puede volver a crear;
    - factura de daños de una renta en `invoice`: vuelve a `checking`.
    """
    _inherit = "account.move"

    is_rental_damage_invoice = fields.Boolean(
        string="Rental Damage Invoice", readonly=True, copy=False,
        help="Created when checking in a rented vehicle, for missing accessories and damage.")

    def button_cancel(self):
        rental_moves = self.filtered("fleet_rent_id")
        others = self - rental_moves
        result = super(AccountMove, others).button_cancel() if others else True
        for move in rental_moves:
            contract = move.fleet_rent_id
            before = contract.read(list(RESTORED_CONTRACT_FIELDS))[0]
            result = super(AccountMove, move).button_cancel()
            contract.write({name: before[name] for name in RESTORED_CONTRACT_FIELDS})
            move._reopen_rental_after_cancel()
        return result

    def _reopen_rental_after_cancel(self):
        contract = self.fleet_rent_id
        if contract.state == "running" and self.is_first_invoice:
            contract.first_invoice_created = False
        elif contract.state == "invoice" and self.is_rental_damage_invoice:
            contract.state = "checking"
