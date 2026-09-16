# cobro-unal

Skill de Claude Code para armar el paquete mensual de cobro de órdenes contractuales de la
Universidad Nacional de Colombia.

Diligencia los tres formatos oficiales, calcula cuánto hay que pagar de seguridad social y agrupa
cada contrato en un PDF listo para radicar.

## Qué hace

El trabajo va en dos fases, con una pausa deliberada en el medio.

**Fase 1A — el monto.** Lee los contratos, pregunta lo mínimo que falta y devuelve **cuánto pagar
de seguridad social**. Solo cuatro datos determinan ese número: valor del contrato, fechas de
ejecución, clase de riesgo ARL y si el contratista es pensionado.

**Fase 1B — los formatos.** Diligencia la certificación cedular, la constancia de cumplimiento y
el informe de ejecución. Todo menos los tres campos que dependen de la planilla.

**Pausa.** Hasta acá se llega sin planilla. El proceso se detiene y espera.

**Fase 2 — cierre.** Con la planilla y los certificados de ARL adjuntos, valida que lo pagado
cubra lo liquidado, completa los campos pendientes y arma un PDF por contrato.

## Estructura

```
Contratos/   las órdenes contractuales en PDF
Anexos/      planilla de seguridad social, certificados de ARL, soportes
Formatos/    las plantillas oficiales en blanco
Cobros/      lo que genera la skill, un directorio por periodo
```

Las tres primeras las llenás vos. `Cobros/` se arma sola.

## Formatos que diligencia

| Código | Documento | Alcance |
|---|---|---|
| `U-FT-12.010.069` | Certificación determinación cedular Rentas de Trabajo | Uno por periodo, con todos los contratos vigentes |
| `U.FT.12.010.053` | Constancia de cumplimiento contractual | Uno por contrato |
| `U.FT.12.011.020` | Informe de ejecución de actividades | Uno por contrato |

## Cómo se usa

```
/cobro-unal
```

Lo primero que pregunta es el periodo, en formato `mm/yyyy`. De ahí en adelante pregunta de a una
cosa por vez, y solo lo que no puede sacar de los contratos.

Para retomar un periodo pausado alcanza con pedírselo: lee el `ESTADO.md` del periodo y entra
directo en la fase que corresponda.

## Requisitos

- macOS con **Microsoft Excel** y **Microsoft Word** instalados.
- `poppler` para leer PDFs (`brew install poppler`).
- El entorno de Python se crea solo con `.claude/skills/cobro-unal/assets/setup.sh`.

Excel y Word se manejan por AppleScript en vez de con librerías de terceros. La razón es concreta:
`openpyxl` no recalcula fórmulas, así que el libro saldría con la sección de aportes en blanco —
justo el número que hay que pagar. Excel recalcula y devuelve el valor real.

> Word y Excel no pueden escribir fuera del directorio del usuario: sus llamadas se cuelgan
> esperando un permiso que no se ve. Todo lo generado vive bajo `$HOME`.

## Agentes

La skill coordina; el trabajo lo hacen cuatro agentes.

| Agente | Responsabilidad |
|---|---|
| `cobro-extractor` | Lee contratos y anexos, arma el registro, reporta qué falta |
| `cobro-excel` | Diligencia la certificación cedular y devuelve los aportes |
| `cobro-documentos` | Genera constancia e informe de cada contrato |
| `cobro-paquete` | Une cada paquete en un PDF y verifica que esté completo |

## Reglas que no se negocian

- **Nada se inventa.** Lo que no está en un documento se pregunta. Las fechas no se deducen de
  la fecha de la orden más el plazo: eso falsearía el monto a pagar.
- **El monto va primero.** Es lo que se necesita para pagar la planilla.
- **La validación es bloqueante.** Si lo pagado en la planilla no cubre lo liquidado, no se arma
  el paquete.
- **Los diligenciados quedan sueltos y agrupados.** El `.docx`, el PDF individual y el paquete
  conviven. No hay paso de limpieza.

## Documentación

- [`SKILL.md`](.claude/skills/cobro-unal/SKILL.md) — el contrato de ejecución.
- [`references/mapa-campos.md`](.claude/skills/cobro-unal/references/mapa-campos.md) — celda por
  celda, de dónde sale cada dato.
- [`references/reglas.md`](.claude/skills/cobro-unal/references/reglas.md) — vigencia, meses,
  porcentajes de avance, ARL y validaciones.

## Aviso

Este repositorio contiene **solo la automatización y las plantillas oficiales en blanco**. No
incluye contratos, planillas, certificados ni entregables: esos llevan datos personales y, en el
caso de los productos, información sujeta a la cláusula de confidencialidad de las órdenes
contractuales. Van en `Contratos/` y `Anexos/`, que están excluidos del control de versiones.

## Licencia

Apache-2.0. Los formatos de `Formatos/` son documentos oficiales de la Universidad Nacional de
Colombia y se incluyen en blanco, tal como los distribuye la institución.
