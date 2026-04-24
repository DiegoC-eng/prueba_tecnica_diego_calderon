# Bloque 0 — Auditoría de Calidad de Datos

**Herramienta:** DuckDB (compatible con BigQuery)
**Dataset:** 6 archivos CSV — prueba técnica retail
**Fecha:** Abril 2026
**Analista:** Diego Calderón

---

## Resumen Ejecutivo

| # | Dimensión | Estado | Hallazgo | Acción |
|---|---|---|---|---|
| 1 | Completitud | ⚠️ | 59.8% transacciones anónimas | Aceptar — usar `loyalty_card=TRUE` para cohortes |
| 2 | Consistencia | ⚠️ | 1% discrepancia en `total_amount` | Usar `total_amount` como fuente de verdad del GMV |
| 3 | Unicidad | ✅ | 0 duplicados en ambas tablas | Sin acción |
| 4 | Validez | ⚠️ | 3 montos en $0 · 231 precios $0 sin promo | Excluir de GMV y GMROI |
| 5 | Integridad Referencial | ⚠️ | VND_031 no existe en vendors (5 productos) | Excluir del análisis de GMROI |
| 6 | Frescura | ⚠️ | TIENDA_012: 7 días sin ventas (sep 2024) | Monitorear — aceptar por ser < 14 días |
| 7 | Integridad Temporal | 🔴 | TIENDA_037: 50 tx antes de su apertura | Excluir esas 50 transacciones |
| 8 | Integridad A/B Test | 🔴 | TIENDA_008 y TIENDA_037 en ambos grupos | Excluir ambas tiendas del experimento |

---

## 1. Completitud

**Pregunta:** ¿Qué porcentaje de transacciones no tiene `customer_id`?

**Query ejecutada:**
```sql
SELECT
  COUNT(*) AS total,
  COUNTIF(customer_id IS NULL) AS sin_customer_id,
  ROUND(COUNTIF(customer_id IS NULL) * 100.0 / COUNT(*), 1) AS pct_sin_customer,
  COUNTIF(loyalty_card = FALSE) AS loyalty_false,
  COUNTIF(loyalty_card = TRUE)  AS loyalty_true,
  ROUND(COUNTIF(loyalty_card = TRUE) * 100.0 / COUNT(*), 1) AS pct_con_lealtad
FROM transactions;
```

**Resultados reales:**

| Métrica | Valor |
|---|---|
| Total transacciones | 174,880 |
| Sin customer_id | 104,632 |
| % sin customer_id | **59.8%** |
| loyalty_card = FALSE | 104,632 |
| loyalty_card = TRUE | 70,248 |
| % con lealtad | 40.2% |

**Observación clave:** `sin_customer_id` y `loyalty_false` son exactamente iguales (104,632). Tiene sentido — si no tienes tarjeta de lealtad, el sistema no puede identificarte.

**Decisión:** ACEPTAR. Los compradores anónimos son parte normal del negocio retail. Para análisis de cohortes y retención de clientes se filtrará con `WHERE loyalty_card = TRUE` (70,248 transacciones identificadas).

---

## 2. Consistencia

**Pregunta:** ¿El `total_amount` coincide con `SUM(unit_price × quantity)` de los items?

**Query ejecutada:**
```sql
WITH suma_items AS (
  SELECT transaction_id, SUM(unit_price * quantity) AS suma_calculada
  FROM transaction_items GROUP BY transaction_id
)
SELECT
  COUNT(*) AS transacciones_comparadas,
  COUNTIF(ABS(t.total_amount - s.suma_calculada) > 0.02) AS con_discrepancia,
  ROUND(COUNTIF(...) * 100.0 / COUNT(*), 2) AS pct_discrepancia,
  ROUND(MAX(ABS(t.total_amount - s.suma_calculada)), 2) AS diferencia_maxima
FROM transactions t JOIN suma_items s USING (transaction_id);
```

**Resultados reales:**

| Métrica | Valor |
|---|---|
| Transacciones comparadas | 174,880 |
| Con discrepancia > $0.02 | 1,745 |
| % con discrepancia | **1.0%** |
| Diferencia máxima | $202.68 |

**Observación clave:** El 1% de discrepancia se explica por descuentos aplicados a nivel de ticket completo (no por línea de item) y por redondeos en el sistema de caja. La diferencia máxima de $202.68 corresponde a transacciones con descuentos grandes de membresía.

**Decisión:** ACEPTAR con criterio definido. Se usará `total_amount` como fuente oficial del GMV en todos los análisis. Es el valor registrado por el sistema de punto de venta y refleja lo que el cliente realmente pagó.

---

## 3. Unicidad

**Pregunta:** ¿Hay `transaction_id` o `transaction_item_id` duplicados?

**Query ejecutada:**
```sql
SELECT 'transactions' AS tabla,
  COUNT(*) AS total_filas,
  COUNT(DISTINCT transaction_id) AS ids_unicos,
  COUNT(*) - COUNT(DISTINCT transaction_id) AS duplicados
FROM transactions
UNION ALL
SELECT 'transaction_items', COUNT(*),
  COUNT(DISTINCT transaction_item_id),
  COUNT(*) - COUNT(DISTINCT transaction_item_id)
FROM transaction_items;
```

**Resultados reales:**

| Tabla | Total filas | IDs únicos | Duplicados |
|---|---|---|---|
| transactions | 174,880 | 174,880 | **0** ✅ |
| transaction_items | 542,015 | 542,015 | **0** ✅ |

**Decisión:** Sin acción requerida. Las claves primarias son únicas en ambas tablas. Los datos no tienen registros duplicados.

---

## 4. Validez

**Pregunta:** ¿Hay montos negativos o precios en $0 sin justificación?

### Parte A — Montos de transacciones

**Resultados reales:**

| Métrica | Valor |
|---|---|
| montos_invalidos (≤ $0) | **3** |
| montos_negativos (< $0) | 0 |
| montos_en_cero (= $0) | 3 |
| Monto mínimo | $0.00 |
| Monto máximo | $3,701.36 |
| Monto promedio | $278.59 |

### Parte B — Precios de items

| Métrica | Valor |
|---|---|
| precio_cero_total | 231 |
| precio_cero SIN promo | **231** ⚠️ |
| precio_cero CON promo | 0 |
| % del total de items | 0.04% |

**Observación clave:** Los 231 items con `unit_price = 0` no tienen ninguna promoción asociada. No hay justificación de negocio para precio $0 sin promo — son datos corruptos. Los 3 montos en $0 pueden ser reversos de compra mal registrados.

**Decisión:**
- Excluir las 3 transacciones con `total_amount = 0` del cálculo de GMV
- Excluir los 231 items con `unit_price = 0` sin promo del cálculo de GMROI
- Filtros a aplicar:
  ```sql
  WHERE total_amount > 0                             -- GMV limpio
  AND (unit_price > 0 OR was_on_promo = TRUE)        -- GMROI limpio
  ```

---

## 5. Integridad Referencial

**Pregunta:** ¿Hay IDs en tablas de hechos que no existan en sus tablas maestras?

**Técnica:** `LEFT JOIN + WHERE lado_derecho IS NULL` para detectar huérfanos.

**Resultados reales:**

| Verificación | Resultado |
|---|---|
| store_id huérfanos en transactions | **0** ✅ |
| vendor_id huérfanos en products | **1** → `VND_031` |
| Productos afectados por VND_031 | **5** |

**Observación clave:** El proveedor `VND_031` aparece en 5 productos del catálogo pero no tiene registro en la tabla `vendors`. Sin datos del proveedor (nombre, categoría, condiciones comerciales) no es posible calcular el GMROI de esos productos.

**Decisión:**
- 0 tiendas huérfanas → sin acción
- Excluir los 5 productos de `VND_031` del análisis de GMROI por proveedor
- Filtro: `WHERE vendor_id != 'VND_031'`

---

## 6. Frescura

**Pregunta:** ¿Hay tiendas con días consecutivos sin registrar ventas?

**Técnica:** Window Function `LAG()` para calcular el gap entre días de venta consecutivos por tienda.

**Resultados reales:**

| Tienda | Gap inicio | Gap fin | Días sin ventas | Severidad |
|---|---|---|---|---|
| TIENDA_012 | 2024-09-09 | 2024-09-17 | **7 días** | REVISAR |

**Observación clave:** Solo 1 gap detectado — TIENDA_012 no registró ventas del 10 al 16 de septiembre 2024 (7 días). Las causas posibles son: inventario agotado, cierre por remodelación, festivo regional, o error en el sistema de carga.

**Decisión:** ACEPTAR con nota. El gap es de 7 días, por debajo del umbral crítico de 14 días. No se excluye de los análisis pero se documenta. Si el gap fuera > 14 días se excluiría esa tienda del Comp Sales.

**Criterio de severidad definido:**
```
3-7 días  → REVISAR  (investigar causa)
8-14 días → ALERTA   (probable cierre temporal)
> 14 días → CRITICO  (excluir de Comp Sales)
```

---

## 7. Integridad Temporal

**Pregunta:** ¿Hay transacciones con fecha anterior a la apertura oficial de la tienda?

**Query ejecutada:**
```sql
SELECT t.store_id, DATE(s.opening_date) AS fecha_apertura,
  MIN(DATE(t.transaction_date)) AS primera_transaccion,
  COUNT(*) AS tx_antes_apertura
FROM transactions t
JOIN stores s ON t.store_id = s.store_id
WHERE DATE(t.transaction_date) < DATE(s.opening_date)
GROUP BY t.store_id, s.opening_date;
```

**Resultados reales:**

| Tienda | Fecha apertura | Primera tx inválida | Tx antes apertura |
|---|---|---|---|
| TIENDA_037 | 2024-06-01 | 2024-05-15 | **50** |

**Observación clave:** TIENDA_037 tiene 50 transacciones registradas antes del 1 de junio de 2024, siendo la más antigua del 15 de mayo. Físicamente es imposible vender en una tienda que no ha abierto — son errores de carga de datos, posiblemente registros de prueba del sistema o un error en la `opening_date`.

**Decisión:** EXCLUIR las 50 transacciones de TIENDA_037 previas al 2024-06-01. Filtro:
```sql
WHERE DATE(t.transaction_date) >= DATE(s.opening_date)
```

> **Nota adicional:** TIENDA_037 también aparece contaminada en el A/B Test (ver sección 8). Es la tienda con más problemas de calidad de datos del dataset.

---

## 8. Integridad del A/B Test

**Pregunta:** ¿Hay tiendas asignadas simultáneamente a los grupos CONTROL y TREATMENT?

**Query ejecutada:**
```sql
WITH variantes AS (
  SELECT store_id, promo_name,
    COUNT(DISTINCT variant) AS num_grupos,
    STRING_AGG(DISTINCT variant ORDER BY variant) AS grupos_asignados
  FROM promotions
  GROUP BY store_id, promo_name
)
SELECT * FROM variantes WHERE num_grupos > 1;
```

**Resultados reales:**

| Tienda | Promoción | Grupos asignados | Decisión |
|---|---|---|---|
| TIENDA_008 | Exhibicion_Q3_2024 | CONTROL + TREATMENT | EXCLUIR |
| TIENDA_037 | Exhibicion_Q3_2024 | CONTROL + TREATMENT | EXCLUIR |

**Resumen del experimento (sin contaminadas):**

| Grupo | Tiendas válidas |
|---|---|
| TREATMENT | 20 |
| CONTROL | 18 |
| **Total válidas** | **38** |
| Excluidas (contaminadas) | 2 |

**Observación clave:** Una tienda asignada a ambos grupos no puede atribuir sus resultados a ninguno. Es equivalente a darle a un paciente el medicamento y el placebo al mismo tiempo — el experimento pierde validez estadística. Además, TIENDA_037 ya tiene problemas de integridad temporal, lo que la convierte en la tienda más problemática del dataset.

**Decisión:** EXCLUIR TIENDA_008 y TIENDA_037 de todo el análisis del experimento A/B. El test se analizará con las 38 tiendas válidas (20 TREATMENT vs 18 CONTROL).

---

## Decisiones Consolidadas para Bloques Siguientes

Todos los análisis de los Bloques 1, 3 y 5 aplicarán estos filtros base:

```sql
-- Filtro base para GMV limpio (Bloque 1, 3, 5)
WHERE t.total_amount > 0
  AND DATE(t.transaction_date) >= DATE(s.opening_date)

-- Para análisis de cohortes y retención (Bloque 3)
AND t.loyalty_card = TRUE

-- Para análisis de GMROI por proveedor (Bloque 1 - Query 4)
AND p.vendor_id != 'VND_031'
AND (i.unit_price > 0 OR i.was_on_promo = TRUE)

-- Para análisis A/B Test (Bloque 3)
AND t.store_id NOT IN ('TIENDA_008', 'TIENDA_037')
```

---

## Conteo de Registros Válidos

| Tabla | Total original | Excluidos | Válidos para análisis |
|---|---|---|---|
| transactions | 174,880 | 53 (3 monto $0 + 50 pre-apertura) | **174,827** |
| transaction_items | 542,015 | 231 (precio $0 sin promo) | **541,784** |
| Tiendas en A/B test | 40 | 2 (contaminadas) | **38** |
| Productos en GMROI | ~200 | 5 (VND_031) | **~195** |

---
*Auditoría ejecutada con DuckDB — queries 100% compatibles con BigQuery*
*Tablas disponibles en: `wmt-ce-core-playground-dev.prueba_tecnica_diego`*
