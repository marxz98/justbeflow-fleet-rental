# -*- coding: utf-8 -*-
{
    "name": "justbeflow — Fleet Rental fixes",
    "version": "19.0.1.5.0",
    "category": "Human Resources/Fleet",
    "summary": "Arreglos por herencia sobre fleet_rental (Cybrosys) para Odoo 19",
    "description": """Correcciones a fleet_rental sin tocar su código.

Este es el sitio donde van los arreglos a fleet_rental: se aplican por
herencia, de modo que actualizar el módulo de Cybrosys no los pisa y
desinstalar este los retira.

Unicidad de VIN y placa. fleet_rental 19.0.1.0.1 declara ambas reglas con
`_sql_constraints`, un atributo que Odoo 19 ya no respeta, así que la
restricción no llega nunca a la base de datos y se pueden crear dos vehículos
con la misma placa o el mismo VIN. Se replican con la API vigente
(models.Constraint). PostgreSQL admite varios NULL en una columna UNIQUE, así
que los vehículos sin placa ni VIN no quedan bloqueados.

Depende de fleet_rental a propósito: el módulo `fleet` del core no declara esas
restricciones, y añadirlas donde no hay rentas sería un cambio de comportamiento
que Odoo no hace. El alcance exacto es "restaurar lo que fleet_rental pretendía".

Sin acceso de alquiler a ir.cron. fleet_rental concede escritura y creación
sobre ir.cron a sus grupos de usuario y manager, con lo que cualquiera de ellos
podía crear crons o lanzarlos con "Ejecutar ahora" (y duplicar facturas del
cron de rentas). Se desactivan esas dos ACL.

Integridad de reservas. Cada reserva queda ligada a su contrato y se borra con
él o con su vehículo; la disponibilidad se comprueba contra todas las reservas
del vehículo, también al extender, y extender solo toca la reserva propia. Las
constraints del contrato admiten escrituras en lote y validan las horas HH:MM.

Facturación y cierre. Las facturas de renta usan el producto de Ajustes (su
variante, no un id de plantilla), el diario de ventas de la compañía y líneas
con vehículo, placa y periodo. Cerrar guarda la fecha real de devolución sin
pisar la contratada y factura cada accesorio faltante y el daño por separado.
El cron solo deja borradores, uno por periodo aunque se ejecute dos veces, y no
envía correo. Cancelar una factura ya no reabre contratos cerrados.

Cancelar sin el grupo de rentas. fleet_rental busca el contrato en cada
cancelación, también de facturas que no son de renta, así que un usuario de
facturación sin el grupo de rentas no podía cancelar ni anular ninguna factura.
Facturación puede leer los contratos, sin editarlos; cancelar una factura de
renta sigue exigiendo el grupo de rentas, porque cambia el contrato.

Código fuente. fleet_rental y los módulos beflow_fleet_rental_* son AGPL-3: el
menú de rentas enlaza al repositorio público con el código que corre (§13).
""",
    "author": "justbeflow.com",
    "website": "https://justbeflow.com",
    "license": "AGPL-3",
    "depends": ["fleet_rental"],
    "data": [
        "security/fleet_rental_acl_overrides.xml",
        "security/ir.model.access.csv",
        "views/source_code_menu.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
