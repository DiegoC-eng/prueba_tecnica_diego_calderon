# Bloque 0 — Auditoría de Calidad de Datos

**Fecha de auditoría:** 2026-04-23 14:19
**Dataset:** Enero 2024 – Junio 2025 | 40 tiendas | 5 países | 4 formatos

## Resumen del Dataset

| Tabla | Registros | Columnas |
|---|---|---|
| stores | 40 | 8 |
| products | 200 | 7 |
| vendors | 30 | 5 |
| store_promotions | 42 | 6 |
| transactions | 174,880 | 8 |
| transaction_items | 542,015 | 6 |

---

## Hallazgos por Dimensión

### 🔍 Completitud: ¿Qué porcentaje de transacciones no tiene customer_id?

**Evidencia:** 104,632 de 174,880 transacciones (59.8%) no tienen customer_id. Las restantes 70,248 (40.2%) tienen customer_id.

**Decisión:** ACEPTAR — El ~60% sin customer_id corresponde a compradores sin tarjeta de lealtad. Se tratarán como clientes anónimos. Para análisis de cohortes se usará solo loyalty_card=TRUE.

---

### 🔍 Completitud: ¿Qué porcentaje de transacciones tiene loyalty_card = FALSE?

**Evidencia:** 104,632 transacciones (59.8%) tienen loyalty_card=FALSE. 70,248 (40.2%) tienen loyalty_card=TRUE. Consistencia con customer_id nulo: 0 diferencia.

**Decisión:** ACEPTAR — loyalty_card=FALSE son compradores sin programa de lealtad. La diferencia con customer_id nulo indica que algunos clientes con tarjeta no se identificaron en caja.

---

### 🔍 Consistencia: ¿El total_amount coincide con la suma de unit_price × quantity en transaction_items?

**Evidencia:** Se compararon 174,880 transacciones con sus items. 1,745 (1.0%) tienen discrepancia > $0.02. Diferencia máxima: $202.68. Mediana de discrepancias: $8.52.

**Decisión:** ALERTA — Si la discrepancia es < 1% se acepta (redondeos/descuentos de nivel transacción). Para análisis de GMV se usará total_amount como fuente de verdad. Se excluirán transacciones con discrepancia > $10 si las hay.

---

### 🔍 Unicidad: ¿Existen transaction_id duplicados?

**Evidencia:** transactions.csv: 0 transaction_id duplicados de 174,880 total. transaction_items.csv: 0 transaction_item_id duplicados de 542,015 total.

**Decisión:** IGNORAR si = 0. Si hay duplicados, se deduplica por transaction_id manteniendo el último registro.

---

### 🔍 Validez: ¿Hay total_amount negativos o cero?

**Evidencia:** 3 transacciones tienen total_amount ≤ 0 (0.00% del total).

**Decisión:** EXCLUIR — Total negativo indica reverso/devolución o error de carga. Se excluirán del análisis de GMV pero se documentarán por separado.

---

### 🔍 Validez: ¿Hay unit_price = 0 con was_on_promo = FALSE?

**Evidencia:** 231 items tienen unit_price=0 en total. De estos, 231 tienen was_on_promo=FALSE (sospechoso) y 0 tienen was_on_promo=TRUE (posible item regalo/promo).

**Decisión:** MARCAR COMO ALERTA — unit_price=0 con was_on_promo=FALSE es anómalo. Se excluyen del cálculo de GMV y GMROI. Se notifica al equipo de datos.

---

### 🔍 Integridad Referencial: ¿Hay store_id en transactions que no existan en stores?

**Evidencia:** 0 store_id huérfanos encontrados: Ninguno. Afecta 0 transacciones.

**Decisión:** EXCLUIR transacciones con store_id sin registro en stores. Si es 0, sin acción requerida.

---

### 🔍 Integridad Referencial: ¿Hay vendor_id en products que no existan en vendors?

**Evidencia:** 1 vendor_id huérfanos: {'VND_031'}. Afecta 5 productos.

**Decisión:** EXCLUIR productos sin proveedor registrado para análisis de GMROI. Se documenta como alerta de gobernanza.

---

### 🔍 Frescura: ¿Hay tiendas con gaps de días consecutivos sin transacciones? ¿Son esperables o sospechosos?

**Evidencia:** 1 gaps detectados en 1 tiendas. Gap máximo: 7 días. Gaps > 1 semana: 1 (potencialmente sospechosos).

**Decisión:** INVESTIGAR gaps > 7 días — podrían ser cierres temporales (inventario, festivos) o fallas en el envío de datos. Los gaps de 1-2 días en domingos/festivos son esperables. Gaps > 14 días se marcan como ALERTA y se excluyen del cálculo de Comp Sales.

---

### 🔍 Integridad Temporal: ¿Existe alguna tienda con transacciones anteriores a su opening_date?

**Evidencia:** 50 transacciones tienen fecha anterior a la opening_date de su tienda. Tiendas afectadas: 1.

**Decisión:** EXCLUIR — Transacciones previas a apertura son errores de carga. Se eliminan del análisis.

---

### 🔍 A/B Test: ¿Hay tiendas asignadas simultáneamente a CONTROL y TREATMENT en store_promotions?

**Evidencia:** 2 tienda(s) están asignadas a ambos grupos en la misma promoción:       store_id          promo_name
7   TIENDA_008  Exhibicion_Q3_2024
36  TIENDA_037  Exhibicion_Q3_2024.

**Decisión:** EXCLUIR tiendas con doble asignación del análisis A/B. Contaminan los resultados del test al pertenecer a ambos grupos.

---

## Resumen de Decisiones para Bloques Siguientes

| Hallazgo | Acción |
|---|---|
| ~60% sin customer_id | Aceptar, usar loyalty_card=TRUE para cohortes |
| Discrepancias total_amount vs items | Usar total_amount como fuente de verdad |
| Duplicados de transaction_id | Deduplicar si existen |
| total_amount ≤ 0 | Excluir del análisis de GMV |
| unit_price=0 sin promo | Excluir de GMROI, marcar alerta |
| Store_id huérfanos | Excluir transacciones sin tienda |
| Vendor_id huérfanos | Excluir de análisis GMROI |
| Gaps > 14 días | Excluir de Comp Sales, investigar |
| Transacciones pre-apertura | Excluir |
| Tiendas en ambos grupos A/B | Excluir del experimento |

---

*Auditoría generada automáticamente por `bloque0_audit.py`*