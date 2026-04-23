# Bloque 2 — Modelado de Datos + Diseño de Pipeline

**Autor:** Diego A. Calderón C.  
**Dataset:** Retail Multiformato Centroamérica | Ene 2024 – Jun 2025

---

## Parte A — Modelo Dimensional (Star Schema)

> El diagrama visual está en `bloque2_modelo.pdf` (generado en dbdiagram.io).
> A continuación se describe el modelo completo en texto.

### Tablas de Hechos

#### `fact_transactions`
| Campo | Tipo | Descripción |
|---|---|---|
| transaction_id | STRING | PK |
| date_key | INTEGER | FK → dim_date |
| store_key | INTEGER | FK → dim_store |
| customer_key | INTEGER | FK → dim_customer (NULL si anónimo) |
| payment_method | STRING | CASH / CARD / DIGITAL |
| total_amount | FLOAT | GMV de la transacción |
| num_items | INTEGER | Ítems distintos en la transacción |
| loyalty_card | BOOLEAN | Si usó tarjeta de lealtad |
| is_anonymous | BOOLEAN | TRUE si customer_id es NULL |
| status | STRING | COMPLETED / CANCELLED |

#### `fact_transaction_items`
| Campo | Tipo | Descripción |
|---|---|---|
| transaction_item_id | STRING | PK |
| transaction_id | STRING | FK → fact_transactions |
| item_key | INTEGER | FK → dim_product |
| date_key | INTEGER | FK → dim_date |
| store_key | INTEGER | FK → dim_store |
| quantity | INTEGER | Unidades vendidas |
| unit_price | FLOAT | Precio de venta |
| unit_cost | FLOAT | Costo (de products.cost) |
| line_gmv | FLOAT | quantity * unit_price |
| line_cost | FLOAT | quantity * unit_cost |
| gross_margin | FLOAT | line_gmv - line_cost |
| was_on_promo | BOOLEAN | Si el ítem estuvo en promo |

#### `fact_promotions_performance`
| Campo | Tipo | Descripción |
|---|---|---|
| promo_store_key | INTEGER | PK surrogate |
| store_key | INTEGER | FK → dim_store |
| promo_name | STRING | Nombre de la promoción |
| variant | STRING | CONTROL / TREATMENT |
| start_date_key | INTEGER | FK → dim_date |
| end_date_key | INTEGER | FK → dim_date |
| promo_type | STRING | EXHIBICION / PRECIO / etc. |

---

### Tablas de Dimensiones

#### `dim_date` — Dimensión tiempo
| Campo | Tipo |
|---|---|
| date_key | INTEGER (YYYYMMDD) |
| full_date | DATE |
| year | INTEGER |
| quarter | INTEGER |
| month | INTEGER |
| month_name | STRING |
| week_of_year | INTEGER |
| day_of_week | INTEGER |
| is_weekend | BOOLEAN |
| is_holiday | BOOLEAN |
| fiscal_period | STRING |

#### `dim_store` — Dimensión tienda
| Campo | Tipo |
|---|---|
| store_key | INTEGER |
| store_id | STRING |
| store_name | STRING |
| country | STRING |
| city | STRING |
| region | STRING |
| format | STRING |
| size_sqm | FLOAT |
| opening_date | DATE |
| months_open | INTEGER (calculado) |
| is_comparable | BOOLEAN (≥13 meses) |

#### `dim_product` — Dimensión producto
| Campo | Tipo |
|---|---|
| item_key | INTEGER |
| item_id | STRING |
| item_name | STRING |
| brand | STRING |
| category | STRING |
| department | STRING |
| vendor_key | INTEGER |
| standard_cost | FLOAT |

#### `dim_vendor` — Dimensión proveedor
| Campo | Tipo |
|---|---|
| vendor_key | INTEGER |
| vendor_id | STRING |
| vendor_name | STRING |
| country | STRING |
| tier | STRING |
| is_shared_catalog | BOOLEAN |

#### `dim_customer` — Dimensión cliente (solo loyalty)
| Campo | Tipo |
|---|---|
| customer_key | INTEGER |
| customer_id_hashed | STRING (SHA-256, ver gobernanza) |
| cohort_month | DATE |
| first_store_key | INTEGER |
| first_country | STRING |
| loyalty_since | DATE |

---

## Justificación de Decisiones de Diseño

### Decisión 1: ¿Cómo modelar el 60% de transacciones sin customer_id?

**Problema:** 104,632 de 174,880 transacciones (59.8%) no tienen customer_id.  
**Opción A:** Excluirlas de `dim_customer`.  
**Opción B:** Crear un customer_key especial = 0 ("Cliente Anónimo").  
**Decisión: Opción B + columna `is_anonymous = TRUE` en `fact_transactions`.**

- Mantiene la integridad referencial del modelo (no NULLs en FKs).
- Permite consultas como `WHERE NOT is_anonymous` para análisis de lealtad.
- Permite agregar GMV total sin perder transacciones anónimas (que son parte del negocio).

### Decisión 2: Dos tablas de hechos en lugar de una

**Problema:** Necesitamos análisis a nivel de transacción (Comp Sales, ticket) Y a nivel de ítem (GMROI, quiebres de stock, basket analysis).  
**Decisión: Dos facts (`fact_transactions` + `fact_transaction_items`) con granularidad diferente.**

- `fact_transactions`: granularidad = 1 fila por ticket. Óptimo para KPIs de tienda.
- `fact_transaction_items`: granularidad = 1 fila por línea. Óptimo para KPIs de producto.
- Evita doble conteo al calcular GMV (usando solo `fact_transactions.total_amount`).
- En BigQuery, las tablas de hechos grandes se particionan por `date_key` y se clusteran por `store_key`.

### Decisión 3: `gross_margin` desnormalizado en `fact_transaction_items`

**Problema:** Calcular margen requiere JOIN entre items y products en cada query de GMROI.  
**Decisión: Pre-calcular `unit_cost`, `line_cost` y `gross_margin` en la tabla de hechos.**

- Rompe levemente la 3NF pero es una práctica estándar en Data Warehousing (Kimball).
- Reduce complejidad de queries analyíticas en un 40-50%.
- El costo se congela al momento de la venta (historial de precios correcto si cambia el costo).
- Ahorra costos de compute en BigQuery (menos JOINs = menos bytes escaneados).

### Decisión 4: `dim_date` como dimensión separada (no solo timestamp)

**Decisión:** Dimensión fecha completa con atributos de negocio (festivos, semana fiscal, temporada).  
**Justificación:** Permite filtros en dashboards sin calcular en runtime. Crítico para Comp Sales YoY y análisis de estacionalidad.

---

## Parte B — Diseño del Pipeline ETL/ELT

```
FUENTE (Sistemas POS de tiendas)
         │
         ▼  [cada hora]
Ingesta RAW — Cloud Storage / GCS
  │  transactions_{store}_{date}_{hh}.json
  │  transaction_items_{store}_{date}_{hh}.json
         │
         ▼  [Dataflow / dbt]
Capa STAGING (BigQuery - dataset `staging`)
  │  stg_transactions    ← validaciones de calidad (ver Bloque 0)
  │  stg_transaction_items
  │  stg_stores, stg_products, stg_vendors
         │
         ▼  [dbt models]
Capa CORE / DWH (BigQuery - dataset `retail_dwh`)
  │  dim_date, dim_store, dim_product, dim_vendor, dim_customer
  │  fact_transactions
  │  fact_transaction_items
  │  fact_promotions_performance
         │
         ▼  [dbt / BQML]
Capa MARTS (BigQuery - dataset `retail_marts`)
  │  mart_comp_sales
  │  mart_store_productivity
  │  mart_cohort_retention
  │  mart_gmroi
  │  mart_stock_gaps
         │
         ▼  [Looker Studio / Power BI]
DASHBOARD OPERATIVO
```

**Tecnologías sugeridas:**
- **Ingesta:** Cloud Pub/Sub + Dataflow (streaming) O Cloud Scheduler + Cloud Functions (batch/hora)
- **Transformación:** dbt (Data Build Tool) sobre BigQuery
- **Orquestación:** Cloud Composer (Airflow gestionado)
- **Almacenamiento:** BigQuery con particionado por fecha y clustering por store_id
- **Dashboard:** Looker Studio (nativo GCP) o Power BI con conector BigQuery

---

## Parte C — Gobernanza

### ¿Cómo manejarías el retraso de hasta 2 horas en el reporte de ventas?

Se usa una **ventana de tolerancia de 3 horas** en el pipeline:
- El job de carga no se ejecuta hasta 3h después del cierre del día (ej. a las 03:00 AM).
- Para dashboards en tiempo real se usaría una vista `near_realtime` que consulta datos de las últimas 6h con etiqueta `[PARCIAL]`.
- Se agrega un campo `is_final` en `fact_transactions`: FALSE si fue cargado en las primeras 2h, TRUE después de reconciliación.

### ¿Cómo detectarías que una tienda dejó de enviar datos?

```sql
-- Alerta automática: tiendas sin transacciones en las últimas 25 horas
SELECT store_id, MAX(transaction_date) AS last_tx_date
FROM fact_transactions
GROUP BY store_id
HAVING TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(transaction_date), HOUR) > 25;
```
- Este query corre cada hora vía Cloud Scheduler.
- Si devuelve filas, envía alerta por email/Slack al equipo de datos.
- Se considera 25h (no 24h) para dar margen al retraso natural de 2h.

### ¿Cómo harías cargas incrementales sin duplicar transacciones?

- **Merge (UPSERT) en BigQuery** usando `MERGE` statement:
  - Si `transaction_id` ya existe: UPDATE (actualizar `status` si cambió).
  - Si no existe: INSERT.
- Alternativamente: cargar a tabla staging con `transaction_date` como partición y reemplazar solo la partición afectada.
- **Idempotencia garantizada:** si el job falla y se re-ejecuta, no genera duplicados.

### ¿Frecuencia del pipeline para dashboard diario?

| Capa | Frecuencia | Justificación |
|---|---|---|
| RAW (ingesta) | Cada hora | Captura datos con retraso |
| STAGING (validación) | Cada hora | Detecta anomalías rápido |
| CORE/DWH | 1x/día (03:00 AM) | Datos finales del día anterior |
| MARTS | 1x/día (04:00 AM) | Después del DWH |
| Dashboard | Refresh automático a las 06:00 AM | Gerentes lo ven al llegar |

### ¿Cómo protegerías customer_id para privacidad?

1. **Hashing:** `customer_id` se hashea con SHA-256 + salt en el momento de ingesta. El ID original NUNCA llega al DWH.
2. **Acceso restringido:** solo el equipo de CRM accede a la tabla de mapeo (ID original ↔ hash).
3. **Column-level security en BigQuery:** `customer_id` con policy tag `PII_HIGH`. Solo roles autorizados ven el valor real.
4. **Data Masking:** en entornos de desarrollo, `customer_id_hashed` aparece como `CUST_XXXX`.
5. **Cumplimiento:** alineado con políticas internas de privacidad y GDPR/LGPD donde aplique.

### ¿Quién debería ser el data owner de la tabla de transacciones?

- **Data Owner:** VP de Operaciones (negocio) — define qué significa el dato y los SLAs.
- **Data Steward:** Equipo de Analytics/Data Engineering — mantiene calidad y pipelines.
- **Data Custodian:** Equipo de Infraestructura/Cloud — seguridad física y acceso.
- En la práctica: se usa un `OWNERS` archivo en el repositorio dbt con propietarios por tabla.

### ¿Cómo resolverías dos reportes con GMV diferente para la misma tienda y día?

**Proceso de reconciliación:**
1. **Identificar la fuente:** ¿ambos vienen del mismo mart? ¿Uno viene del staging?
2. **Revisar filtros:** ¿uno incluye `status='CANCELLED'` y el otro no? ¿Uno usa `total_amount`, el otro la suma de items?
3. **Trazar el lineage:** con dbt lineage graph o BigQuery Information Schema.
4. **Definir la "Golden Source":** `fact_transactions.total_amount` con `status='COMPLETED'` y `total_amount > 0` es el único GMV oficial.
5. **Documentar la resolución** en el Data Dictionary y crear un test de dbt que valide consistencia.
6. **Comunicar a stakeholders:** cuál reporte es correcto y por qué el otro estaba mal.
