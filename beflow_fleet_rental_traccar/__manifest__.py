# -*- coding: utf-8 -*-
{
    "name": "justbeflow — Fleet Rental × Traccar",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Fleet",
    "summary": "Horas de motor del GPS (Traccar) en los contratos por horas",
    "description": """Puente entre beflow_fleet_rental_ext y fleet_traccar.

Guarda en cada dispositivo de Traccar las horas de motor que publica en el
atributo `hours` de sus posiciones (en milisegundos). Una posición más antigua
que la última aplicada no cambia nada.

En los contratos por horas de motor rellena la lectura inicial al pasar a
"En curso" y la final al Verificar, solo si están vacías (un valor puesto a
mano nunca se pisa) y si la lectura no es menor que la inicial. Deja una nota
en el historial con el valor y la hora de la posición.

Se instala solo cuando están los dos módulos: un cliente sin GPS no arrastra
Traccar.
""",
    "author": "justbeflow.com",
    "website": "https://justbeflow.com",
    "license": "AGPL-3",
    "depends": ["beflow_fleet_rental_ext", "fleet_traccar"],
    "data": [],
    "installable": True,
    "auto_install": True,
    "application": False,
}
