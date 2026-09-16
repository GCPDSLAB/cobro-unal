---
name: cobro-unal
description: "Trigger: cobro UNAL, armar paquete de cobro, cuenta de cobro, constancia de cumplimiento, informe de ejecución, certificación cedular, planilla. Arma el paquete mensual de cobro por contrato."
license: Apache-2.0
metadata:
  author: "Daprosero"
  version: "3.7"
---

## Activation Contract

Se activa al pedir el cobro de un periodo en `Pagos_Unal`: armar el paquete, diligenciar los
formatos, generar constancia / informe / certificación cedular, o **retomar un periodo pausado**
cuando ya se adjuntó la planilla.

## Hard Rules

- **Coordinás, no ejecutás.** Todo el trabajo real lo hacen los agentes. Lo tuyo se limita a:
  pedir el periodo, crear las carpetas, lanzar agentes, preguntar faltantes, comparar dos números
  en la validación de aportes, escribir `ESTADO.md` y reportar.
- **Nunca hagas vos** lo que tiene agente: leer un contrato, diligenciar un formato, exportar un
  PDF o unir un paquete. Ni a mano, ni con un script propio, ni "porque es más rápido".
  Si un agente falla, lo relanzás con la corrección; no lo reemplazás.
- Los scripts de `assets/` los corre **el agente dueño de ese paso**, nunca vos directamente.
- Pedir el periodo `mm/yyyy` **antes** de cualquier otra acción.
- El trabajo va en **dos fases**. La fase 1 llega hasta donde se pueda sin planilla y **se detiene**.
- **El monto a pagar se entrega antes que nada.** Solo 4 datos lo determinan: valor y fechas del
  contrato, clase de riesgo ARL y si el contratista es pensionado. Conseguí esos, corré el Excel,
  **decí cuánto pagar**, y recién después seguí con el resto de las preguntas.
- Nunca retrases el monto por datos que no entran en el cálculo: QUIPU, correo, supervisor,
  actividades, satisfacción y deducciones **no cambian `total_aportes`**.
- Nunca editar `Formatos/`, `Contratos/` ni `Anexos/`: trabajar sobre copias en `Cobros/<yyyy-mm>/`.
- Una subcarpeta por contrato, `Cobros/<yyyy-mm>/<TIPO>-<Nº>-<AÑO>/`, con sus formatos adentro.
- Cada documento diligenciado queda **suelto y además agrupado**: su `.docx`, su `.pdf` individual
  y el PDF del paquete conviven. **Nunca borres un intermedio** después de unir.
- Si la carpeta del periodo ya existe **sin** `ESTADO.md`, crear `-v2`, `-v3`… Nunca sobrescribir.
- **Nunca inventar un dato.** Lo que no salga de contratos ni anexos se pregunta.
- **Nunca preguntar lo que ya se calculó.** El valor del cobro y su número salen del contrato o
  del mensualizado que el Excel usó para la planilla. Si hiciste el cálculo, tenés el dato.
- Preguntar de a una cosa por vez y esperar respuesta.
- Ejecutar los scripts con `.claude/skills/cobro-unal/.venv/bin/python`; crearlo con `assets/setup.sh` si falta.
- Todo archivo generado vive bajo `$HOME`: Word y Excel no pueden escribir en `/tmp` y se cuelgan.

## Decision Gates

| Situación | Acción |
|---|---|
| Existe `Cobros/<yyyy-mm>/ESTADO.md` | Retomar ese periodo en la fase que indique, no crear uno nuevo |
| Un agente devuelve un error o dato faltante | Preguntar lo que falte y **relanzarlo**; nunca hacer su trabajo vos |
| Dato ya resuelto en `Cobros/registro/` | Reusarlo, no volver a preguntar |
| `firmante` ya está en el registro | Confirmarlo igual: puede firmar otro este periodo |
| Hay que llenar actividades ejecutadas | Redactarlas desde las obligaciones y mostrarlas; no preguntarlas en blanco |
| Hay que poner el valor del cobro | Derivarlo del contrato o del mensualizado ya calculado. **Nunca preguntarlo** |
| `pdftotext` devuelve vacío | Contrato escaneado: leerlo con `Read` (visión) |
| Contrato en `contratos_sin_fechas` | Preguntar fechas reales **y** si aplica al periodo. Nunca deducirlas del plazo |
| Más de un certificado ARL en `Anexos/` | Preguntar cuál corresponde a cada contrato |
| Ningún certificado ARL | Preguntar la clase de riesgo por contrato |
| Contratos con riesgos ARL distintos | Cotizar por el más alto, y avisarlo |
| `valor_mensualizado_total <= 95 UVT` | Omitir la sección 3 **del Excel** (deducciones) |
| Falta un dato con `bloquea_calculo: true` | Preguntarlo **ya**: sin él no hay monto |
| Falta un dato con `bloquea_calculo: false` | Dejarlo para la fase 1B, después de dar el monto |
| Falta la planilla | Cerrar fase 1 y esperar. No armar paquetes |
| Sección 3 **del informe** quedó vacía | El contrato no pactó productos: no hay parte 7 y no se pregunta |
| Sección 3 **del informe** declara productos | Preguntar dónde está el soporte de cada uno; si no hay, seguir y dejarlo dicho |
| Varios contratos en el periodo | **Un solo libro** con todos relacionados; un PDF por contrato variando solo `D36` |
| Se piden deducciones (algún checkbox en `SI`) | `D36` es el **mismo** contrato en todas las copias: van a uno solo |

## Execution Steps

### Fase 1A — el monto a pagar, lo antes posible

1. Preguntar el periodo. Crear `Cobros/<yyyy-mm>/` y copiar ahí el Excel de `Formatos/` como
   `certificacion-cedular.xlsx`. **Todavía no** hay subcarpetas: no se sabe qué contratos entran.
2. Lanzar `cobro-extractor`: lee `Contratos/` y `Anexos/`, escribe `Cobros/registro/`,
   devuelve los contratos vigentes y los faltantes.
3. Confirmar con el usuario qué contratos entran al periodo — incluidos los de
   `contratos_sin_fechas`, que el extractor no pudo clasificar — y preguntar **solo lo que
   bloquea el cálculo**: fechas reales de esos contratos, clase de riesgo ARL de cada uno,
   y si es pensionado. Nada más.
4. Lanzar `cobro-excel` con `fase: 1`.
5. **Decir cuánto pagar.** `total_aportes` con su desglose, para que el usuario pague la planilla
   mientras siguen las preguntas. Este número ya es definitivo: no cambia en el resto del proceso.

### Fase 1B — los formatos

6. Preguntar los faltantes restantes, de a uno: QUIPU, correo institucional, **quién firma**,
   adición u otrosí, nivel de satisfacción, deducciones. Guardarlos en el registro.
   **Las actividades ejecutadas no se preguntan**: las redacta `cobro-documentos` desde las
   obligaciones del contrato, y el usuario las revisa después.
   Sobre el firmante: los contratos designan al supervisor *"o quien haga sus veces"*, así que
   preguntar si firma el del contrato o alguien más. Si es otro, pedir nombre, cédula, correo y
   teléfono. Confirmarlo **una vez por periodo**, aunque ya esté en el registro.
7. Crear `Cobros/<yyyy-mm>/<TIPO>-<Nº>-<AÑO>/` por cada contrato a cobrar, con su copia de la
   constancia y del informe.
8. Relanzar `cobro-excel` con `fase: 1` para escribir los datos de identificación que faltaban
   (nombre, documento, correo, QUIPU, tipo y número de orden) y exportar **un PDF del cedular por
   contrato**, variando solo `D36`.
9. Lanzar `cobro-documentos` con `fase: 1` por cada contrato: informe completo y constancia
   completa **salvo el punto 2**, cuyos espacios quedan en blanco.
   Mostrar al usuario las `actividades_redactadas` para que las ajuste si quiere: él firma
   ese documento. Si pide cambios, relanzar el agente con el texto corregido.
10. Mirar `productos_declarados` que devolvió el paso anterior — es la sección 3 del informe.
    Solo si trae productos, preguntar dónde está su soporte. Guardar la ruta en el registro.
    Nunca preguntar por soportes de un contrato que no pactó productos.
11. Escribir `Cobros/<yyyy-mm>/ESTADO.md` con lo hecho, lo pendiente y el monto a pagar.
12. **Detenerse.** Informar cuánto pagar de seguridad social y qué falta adjuntar: la planilla,
   los certificados de ARL y los soportes que el usuario haya señalado. No continuar sin ellos.

### Fase 2 — cuando ya están la planilla y los ARL

13. Relanzar `cobro-extractor` para releer `Anexos/`. Si la planilla o un ARL siguen faltando,
    decir qué y volver a esperar.
14. Validar `total_aportes <= aportes pagados en la planilla`. Si falla, detener y reportar la diferencia.
15. Lanzar `cobro-excel` con `fase: 2`: completa `C42` y `E45` y reexporta el PDF.
16. Lanzar `cobro-documentos` con `fase: 2`: completa el punto 2 de cada constancia y reexporta.
17. Lanzar `cobro-paquete`: un PDF por contrato, con la copia del cedular y los soportes al final.
    Actualizar `ESTADO.md` a completado.

## Output Contract

**Fase 1A:** el monto a pagar con su desglose (salud, pensión, fondo de solidaridad, ARL),
los contratos que lo componen y su valor mensualizado. Nada más: es lo que el usuario necesita
para pagar la planilla.

**Fase 1B:** ruta del periodo, contratos incluidos,
documentos generados por contrato, datos que se preguntaron, y la lista exacta de lo que falta
adjuntar: planilla, certificados de ARL y soportes opcionales.

**Fase 2:** validación de aportes con ambos valores, y por contrato **las dos rutas**: los
documentos sueltos y el paquete agrupado con su número de páginas. Cerrar con lo que queda
pendiente de firma.

## References

- `references/mapa-campos.md` — celdas, coordenadas y fase de cada campo.
- `references/reglas.md` — vigencia, meses, avance, ARL, validaciones y estructura de carpetas.
- `assets/registro.example.json` — estructura de `perfil.json` y `contratos.json`.
- `assets/excel_fill.py`, `assets/docx_fill.py`, `assets/word_pdf.py`, `assets/merge_pdf.py`.
