# Bloque 2 — Modelado de Datos + Diseño de Pipeline

**Autor:** Diego Alberto Calderón Calderón  
**Objetivo:** Star Schema en BigQuery para soporte de KPIs de retail multiformato  

---

## A. Modelo Dimensional — Star Schema

### Tabla de Hechos: `fact_sales`

Granularidad: **una fila por ítem de transacción** (nivel más atómico).  
Esta granularidad permite agregar a cualquier nivel (por día, tienda, producto, proveedor).

| Campo | Tipo | Descripción |
|---|---|---|
| `fact_sale_id` | STRING | PK sintética (transaction_item_id) |
| `transaction_id` | STRING | FK → dim_transaction |
| `date_id` | DATE | FK → dim_date |
| `store_id` | STRING | FK → dim_store |
| `product_id` | STRING | FK → dim_product |
| `customer_id` | STRING | FK → dim_customer (NULLABLE) |
| `promo_id` | STRING | FK → dim_promotion (NULLABLE) |
| `quantity` | INT64 | Unidades vendidas |
| `unit_price` | FLOAT64 | Precio de venta |
| `unit_cost` | FLOAT64 | Costo unitario (desde products.cost) |
| `gross_revenue` | FLOAT64 | quantity × unit_price |
| `gross_margin` | FLOAT64 | gross_revenue - (quantity × unit_cost) |
| `was_on_promo` | BOOL | Si el ítem estaba en promoción |
| `is_returned` | BOOL | Si la transacción fue devuelta |
| `_loaded_at` | TIMESTAMP | Timestamp de carga del pipeline |

### Tabla de Hechos: `fact_ab_test_weekly`

Granularidad: **tienda × semana** (para el análisis A/B).  

| Campo | Tipo | Descripción |
|---|---|---|
| `store_id` | STRING | FK → dim_store |
| `week_start_date` | DATE | FK → dim_date |
| `variant` | STRING | CONTROL / TREATMENT |
| `promo_name` | STRING | Nombre del experimento |
| `gmv_week` | FLOAT64 | GMV semanal |
| `n_transactions` | INT64 | Transacciones en la semana |
| `avg_ticket` | FLOAT64 | Ticket promedio |

---

### Dimensiones

#### `dim_date`
| Campo | Tipo |
|---|---|
| `date_id` | DATE (PK) |
| `day_of_week` | INT64 |
| `week_number` | INT64 |
| `month` | INT64 |
| `quarter` | INT64 |
| `year` | INT64 |
| `is_weekend` | BOOL |
| `is_holiday_cr` | BOOL |
| `fiscal_period` | STRING |

#### `dim_store`
| Campo | Tipo |
|---|---|
| `store_id` | STRING (PK) |
| `store_name` | STRING |
| `country` | STRING |
| `city` | STRING |
| `format` | STRING |
| `region` | STRING |
| `size_sqm` | INT64 |
| `opening_date` | DATE |
| `is_comparable` | BOOL | (apertura < 13 meses antes del período actual) |

#### `dim_product`
| Campo | Tipo |
|---|---|
| `product_id` | STRING (PK) |
| `item_name` | STRING |
| `brand` | STRING |
| `category` | STRING |
| `department` | STRING |
| `vendor_id` | STRING |
| `unit_cost` | FLOAT64 |

#### `dim_vendor`
| Campo | Tipo |
|---|---|
| `vendor_id` | STRING (PK) |
| `vendor_name` | STRING |
| `country` | STRING |
| `tier` | STRING |
| `is_shared_catalog` | BOOL |

#### `dim_customer` (SCD Tipo 1)
| Campo | Tipo |
|---|---|
| `customer_id` | STRING (PK) |
| `first_transaction_date` | DATE |
| `cohort_month` | DATE |
| `total_lifetime_transactions` | INT64 |
| `is_identified` | BOOL |

#### `dim_promotion`
| Campo | Tipo |
|---|---|
| `promo_id` | STRING (PK) |
| `store_id` | STRING |
| `promo_name` | STRING |
| `variant` | STRING |
| `promo_type` | STRING |
| `start_date` | DATE |
| `end_date` | DATE |

---

## A.2. Justificación de Decisiones de Diseño

### Decisión 1: Granularidad a nivel de ítem, no de transacción
**Por qué:** Si la granularidad fuera a nivel de transacción, perderíamos la capacidad de analizar GMROI por proveedor/categoría, el impacto de promociones por SKU, y los quiebres de stock por ítem. El nivel de ítem es el más atómico y permite agregar en cualquier dirección sin pérdida de información.  
**Trade-off:** La tabla de hechos será más grande (~542K filas por 18 meses), pero en BigQuery el costo es de almacenamiento, no de joins (columnar). La partición por `date_id` mitiga el costo de escaneo.

### Decisión 2: Modelar el 60% sin `customer_id` como `dim_customer` con `is_identified = FALSE`
**Por qué:** La alternativa sería dejar `customer_id` NULL en `fact_sales`. El problema: los reportes que filtran clientes sin identificar terminarían con NULLs silenciosos que distorsionan los promedios. Al crear un registro explícito `customer_id = 'ANON'` o simplemente mantener el NULL con un flag `is_identified`, el modelo es transparente y evita pérdida de filas en LEFT JOINs.  
**Decisión final:** `customer_id NULLABLE` en `fact_sales` + `is_identified BOOL` en `dim_customer`. Los análisis de cohortes filtrarán explícitamente `WHERE is_identified = TRUE`.

### Decisión 3: Columna `is_comparable` en `dim_store`
**Por qué:** Las Comp Sales son la métrica más importante del retail. En lugar de recalcular en cada query si una tienda tiene 13+ meses de historia, pre-computamos el flag en la dimensión. Esto evita errores repetidos, mejora la legibilidad de las queries y asegura una definición única de “tienda comparable” en todos los reportes.  
**Actualización:** Este campo se recalcula mensualmente en el pipeline ETL.

### Decisión 4: Pre-calcular `gross_revenue` y `gross_margin` en la tabla de hechos
**Por qué:** YAGNI al revés: estas métricas se usan en TODOS los KPIs (Comp Sales, GMROI, productividad por m²). Calcularlas en tiempo de query con `quantity * unit_price` en cada SELECT genera redundancia, posibles inconsistencias si la fórmula cambia, y penaliza el rendimiento en tablas grandes. Pre-computarlas al momento de carga asegura consistencia y velocidad.  

---

## B. Diseño del Pipeline ETL/ELT

### B.1 ¿Cómo manejar que las tiendas reportan ventas con hasta 2 horas de retraso?

**Estrategia:** El pipeline diario corre a las **06:00 am hora local** (después de las 2 horas de retraso). No se procesan datos del día en curso hasta las 6am del día siguiente. Esto garantiza que las ventas del día D estén completas antes de ser cargadas.

Además, se implementa una **ventana de corrección de 3 días**: si una transacción llega tarde (hasta 3 días después), se inserta/actualiza en BigQuery usando la clave `transaction_id` como idempotente (INSERT OR REPLACE en el merge). Transacciones con más de 3 días de retraso se procesan en una tabla de cuarentena y requieren revisión manual.

### B.2 ¿Cómo detectar automáticamente que una tienda dejó de enviar datos?

**Estrategia:** En cada ejecución del pipeline se verifica:

1. **Monitor de frescura:** Para cada `store_id`, verificar que el `MAX(transaction_date)` sea `≤ ayer` (si es < ayer – 1, la tienda no reporó).
2. **Alerta automática:** Si una tienda lleva más de 24 horas sin transacciones, el pipeline publica una alerta en el canal de Slack de Data Ops y genera un registro en la tabla `monitoring.store_freshness_alerts`.
3. **Dashboard:** El reporte ejecutivo muestra un semaforo de última actualización por tienda.

```
Monitor query (ejecutar al final de cada carga):
SELECT store_id, MAX(transaction_date) AS last_date
FROM fact_sales
GROUP BY store_id
HAVING last_date < CURRENT_DATE - 1
```

### B.3 ¿Cómo hacer cargas incrementales sin duplicar transacciones?

**Estrategia ELT con MERGE:**

1. Los datos llegan a una tabla de staging particionada: `staging.transactions_raw` con columna `_ingested_at TIMESTAMP`.
2. El pipeline ejecuta un **MERGE** (UPSERT) desde staging hacia `fact_sales` usando `transaction_item_id` como clave.
3. Si el `transaction_id` ya existe → UPDATE (para manejar correcciones/devoluciones).
4. Si no existe → INSERT.
5. La tabla de staging se limpia después de cada merge exitoso.

**Idempotencia:** El pipeline puede re-ejecutarse N veces para el mismo día sin generar duplicados, porque el MERGE es idempotente por llave.

### B.4 ¿Frecuencia del pipeline para refresh diario del dashboard?

**Propuesta:**

| Proceso | Frecuencia | Hora |
|---|---|---|
| Ingesta raw desde POS | Cada hora | 24/7 |
| ETL incremental (fact_sales) | Diaria | 06:00 am |
| Recalculo de agregados (vistas materializadas) | Diaria | 07:00 am |
| Refresh del dashboard | Diaria | 08:00 am |
| Monitor de frescura | Cada hora | 24/7 |

El dashboard usa **vistas materializadas** en BigQuery sobre `fact_sales`, refrescadas diariamente. Esto separa la carga del ETL del consumo del dashboard.

---

## C. Gobernanza

### C.1 ¿Cómo proteger `customer_id` para cumplir políticas de privacidad?

**Estrategia de PII:**

1. **Pseudonimización:** El `customer_id` crudo nunca se almacena en `fact_sales`. En su lugar se usa un **hash SHA-256** con salt rotativo: `customer_key = SHA256(customer_id || salt_mensual)`. Esto permite correlación temporal sin exponer el ID original.
2. **Column-level security en BigQuery:** La columna `customer_key` tiene `POLICY_TAG = PII_MEDIUM`. Solo roles con permiso exploto (`data_analyst_pii`, `data_scientist_pii`) pueden ver valores reales; los demás ven `NULL`.
3. **Retención:** Los datos de cliente se retienen por 24 meses y luego se anonimiza el campo permanentemente.
4. **Logs de acceso:** Todos los accesos a columnas PII se registran en Cloud Audit Logs con alertas si se consultan >10,000 registros en una sola query.

### C.2 ¿Quién debería ser el Data Owner de la tabla de transacciones?

**Propuesta de ownership:**

| Rol | Área | Responsabilidad |
|---|---|---|
| **Data Owner** | VP de Finanzas / CFO | Propietario del dato de negocio. Aprueba cambios en la definición de GMV, devolución y status. |
| **Data Steward** | Gerencia de Analytics | Responsable de calidad del dato, documentación y glosario de negocio. |
| **Data Producer** | Ingeniería de Datos | Dueño técnico del pipeline. Responsable de SLAs de frescura y unicidad. |
| **Data Consumer** | Equipos de Operaciones, Merch, Marketing | Uso read-only con roles segmentados por país/formato. |

### C.3 Si dos reportes muestran GMV diferente para la misma tienda y día, ¿cuál es el proceso?

**Proceso de resolución de discrepancias (Data Lineage Investigation):**

1. **Identificar las fuentes:** ¿Cuál es la query exacta de cada reporte? ¿Qué tabla/vista usa cada uno?
2. **Comparar definiciones de GMV:** ¿Uno incluye devoluciones (`status = 'RETURNED'`) y el otro no? ¿Uno usa `total_amount` y el otro `SUM(unit_price * quantity)`?
3. **Verificar filtros de fecha:** ¿Uno usa `transaction_date` y el otro `_loaded_at`? Las 2 horas de retraso pueden crear discrepancias si el corte es a medianoche exacta.
4. **Rastrear hasta raw:** Comparar contra la tabla de staging (`staging.transactions_raw`) como fuente de verdad.
5. **Documentar y estandarizar:** Una vez encontrada la causa, actualizar el **Glosario de Métricas** (Data Catalog) con la definición canónica de GMV. Todos los reportes deben consumir la misma vista certificada `reporting.v_daily_gmv`.
6. **Certificación de reportes:** Solo los reportes que consumen vistas certificadas pueden llamarse "oficiales". Los reportes ad-hoc que usen tablas raw deben llevar un banner de "no certificado".

---

## D. Decisiones que Cambiaría con Más Tiempo

> *Esta sección documenta las limitaciones del diseño actual y las mejoras que implementaría si el scope lo permitiera.*

### D.1 — Tabla de Hechos de Inventario
Actualmente el análisis de quiebres de stock infiere OOS desde gaps de ventas en `fact_sales`. Esto es un proxy, no evidencia directa. Con más tiempo diseñaría una tabla `fact_inventory` con snapshots diarios de stock por tienda-SKU. Eso permitiría distinguir entre:
- "No se vendió porque no había stock" (quiebre real)
- "No se vendió porque no hubo demanda" (baja rotación)

Esta diferencia es crítica para las decisiones de abastecimiento y la Query 5 no puede responderla solo con datos de ventas.

### D.2 — SCD Tipo 2 para `dim_store`
Use SCD Tipo 1 en `dim_store` por simplicidad, lo que significa que si una tienda cambia de formato (ej: un Supermercado que se convierte en Hipermercado) perderíamos la historia. Dado que la cadena opera en 5 países con posibles remodelaciones, el Tipo 2 con fechas de vigencia (`valid_from`, `valid_to`) sería más robusto para el análisis histórico de Comp Sales por formato.

### D.3 — Tabla de Hechos de Promoción Separada
Actualmente las promociones se modelan con un `promo_id` nullable en `fact_sales`. Esto hace difícil calcular el costo de las promociones (cuánto descuento se otorgó) y el ROI de cada campaña. Una tabla `fact_promo_impact` con el descuento en valor absoluto por ítem promocional permitiría un análisis más preciso.

### D.4 — Validación del Costo Unitario
El campo `cost` en `products.csv` genera GMROI sospechosamente bajo (<0.35). Antes de usar este dato en producción, el primer paso sería una sesión de validación con el equipo de Compras para confirmar si `cost` es costo unitario, costo de caja, o costo promedio ponderado. Actualmente el modelo asume que es costo unitario sin haber podido validarlo.
