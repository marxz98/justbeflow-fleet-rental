# -*- coding: utf-8 -*-
import contextvars
from contextlib import contextmanager

from odoo import api, fields, models
from odoo.exceptions import UserError

RESTORED_CONTRACT_FIELDS = ("state", "first_invoice_created")
RENTAL_LINK_FIELDS = ("fleet_rent_id", "is_first_invoice")

# Solo la facturación de rentas liga facturas a contratos y marca días cubiertos (5.5, M1).
# No viaja en el contexto, que lo decide el cliente en cada llamada RPC; una ContextVar no.
_RENTAL_BILLING = contextvars.ContextVar("beflow_rental_billing", default=False)


@contextmanager
def rental_billing():
    token = _RENTAL_BILLING.set(True)
    try:
        yield
    finally:
        _RENTAL_BILLING.reset(token)


def check_rental_billing(env, field_names):
    """Ligar o desligar a mano facturas y contratos ocultaría cobros o deudas del contrato."""
    if field_names and not _RENTAL_BILLING.get():
        raise UserError(env._("Only rental billing can set these invoice fields: %s.", ", ".join(sorted(field_names))))


def fields_set(records, field_names):
    """Al crear se mira el registro, no los valores: los default_* del contexto RPC llegan después."""
    return {name for name in field_names for record in records if record[name]}


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

    fleet_rent_id = fields.Many2one(copy=False)
    is_first_invoice = fields.Boolean(copy=False)
    is_rental_damage_invoice = fields.Boolean(
        string="Rental Damage Invoice", readonly=True, copy=False,
        help="Created when checking in a rented vehicle, for missing accessories and damage.")

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        check_rental_billing(self.env, fields_set(moves, RENTAL_LINK_FIELDS))
        return moves

    def write(self, vals):
        check_rental_billing(self.env, set(RENTAL_LINK_FIELDS) & vals.keys())
        return super().write(vals)

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
