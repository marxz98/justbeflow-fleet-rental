# justbeflow — Fleet Rental (código AGPL-3)

Código fuente de los módulos de renta de flota que corren en justbeflow sobre Odoo 19
Community. Se publica por la licencia AGPL-3 (§13): quien usa el servicio por la red puede
obtener el código que corre. El menú **Rentas → Código fuente** enlaza aquí.

Cada commit de este repositorio es la copia de un commit desplegado de justbeflow, indicado en
su mensaje.

| Módulo | Qué hace |
|---|---|
| `fleet_rental` | Módulo de Cybrosys (AGPL-3), vendorizado sin cambios de código; repo, commit y cambios locales en `fleet_rental/UPSTREAM`. |
| `beflow_fleet_rental_fixes` | Correcciones a `fleet_rental` por herencia: reservas, facturación, cierre y permisos. |
| `beflow_fleet_rental_ext` | Tarifa por día o por horas de motor, cargo de contrato, equipo y operador, calendario de disponibilidad. |
| `beflow_fleet_rental_traccar` | Toma las horas de motor del GPS. Necesita `fleet_traccar` (LGPL-3), de [traccar/traccar-odoo](https://github.com/traccar/traccar-odoo). |

## Instalación

Copia las carpetas en el `addons_path` de un Odoo 19 Community e instala
`beflow_fleet_rental_ext` (arrastra `fleet_rental` y `beflow_fleet_rental_fixes`). El puente con
Traccar es opcional y necesita además `fleet_traccar`.

## Licencia

AGPL-3, ver `LICENSE`. `fleet_rental` © Cybrosys Techno Solutions; los módulos
`beflow_fleet_rental_*` © justbeflow.
