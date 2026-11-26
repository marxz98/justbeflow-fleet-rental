# -*- coding: utf-8 -*-
{
    "name": "justbeflow — Fleet Rental extensions",
    "version": "19.0.1.1.0",
    "category": "Human Resources/Fleet",
    "summary": "Renta por días u horas de motor × tarifa, cargo de contrato, extensiones, equipo, operador y calendario",
    "description": """Funcionalidad de renta de flota que fleet_rental no trae.

Tarifa por unidad. El campo "Rent Cost" de fleet_rental, que estaba oculto, es
la tarifa por día: la factura muestra días × tarifa (11.00 × 1,400.00), con los
días contados de forma inclusiva. Cada periodo recurrente se cobra igual, con
los días que tiene (una semana son 7; un mes, de 28 a 31).

Cargo de contrato. "First Payment" es un cargo aparte, como dice su ayuda en
fleet_rental: va en su propia línea de la factura inicial y solo si es mayor
que 0. Un contrato recurrente sin cargo no tiene factura inicial.

Extensiones. Al confirmar una extensión de un contrato que ya tiene su factura
inicial, se crea un borrador con los días extra × tarifa. Si aún no se ha
facturado, la factura inicial cubre la nueva fecha; si es recurrente, la
cubren sus periodos.

Equipo y operador. En la pestaña "Equipo" cada equipo o servicio adicional
(por ejemplo "Servicio de operador") es una línea con su tarifa, que se factura
con la misma cantidad que la renta en cada factura. El operador del contrato
es un contacto, a título informativo.

Horas de motor. La casilla "Rent By Hour" de fleet_rental pasa a ser "Por
horas de motor": la renta y el equipo no van en la factura inicial sino en la
de cierre, con la cantidad horas finales − horas iniciales, junto a los
faltantes y daños. Cerrar sin lectura final da error; no admite cobro
recurrente. Las horas se corrigen a mano y quedan en el historial. Si se
cancela la factura de cierre, el contrato vuelve a revisión.

Disponibilidad. Menú "Disponibilidad" con un calendario de los contratos que
ocupan un vehículo (reservados, en curso y en revisión), un color por
vehículo; al pulsar un contrato se abre su ficha.

Cada día se cobra una vez. Cada línea de renta por días guarda los días que
cubre, y cada factura cobra solo los que ninguna factura viva cubre: anular
una factura deja sus días pendientes y el cierre cobra todo lo pendiente
(renta y cargo), también si nunca se creó la factura inicial.

Condiciones fijas. Al confirmar quedan fijos el modo, la frecuencia y las
fechas (la de fin solo cambia extendiendo); al facturar, la tarifa y el
cargo; al empezar la renta, el equipo. La tarifa es obligatoria al confirmar
y ningún importe puede ser negativo.

Editar el precio de una línea de factura ya no cambia el cargo del contrato.

Las fechas de cobertura de las líneas (`rental_date_from/to`) solo las pone la
facturación de rentas: a mano o por RPC dejarían días sin cobrar.
""",
    "author": "justbeflow.com",
    "website": "https://justbeflow.com",
    "license": "AGPL-3",
    "depends": ["beflow_fleet_rental_fixes"],
    "data": [
        "security/ir.model.access.csv",
        "security/rental_contract_line_security.xml",
        "views/car_rental_contract_views.xml",
        "views/rental_availability_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
