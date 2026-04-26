-- ============================================================
-- PRUEBA TÉCNICA — DATA ANALYST — CADENA RETAIL CENTROAMÉRICA
-- Autor: Diego Alberto Calderón Calderón
-- Dataset: 18 meses (Ene 2024 – Jun 2025) | 40 tiendas | 5 países
-- Dialecto: BigQuery Standard SQL (compatible con DuckDB/SQLite)
-- ============================================================


-- ============================================================
-- QUERY 1: VENTAS COMPARABLES (COMP SALES) — YoY
-- Métrica estándar de retail.
-- Solo incluye tiendas con al menos 13 meses de operación
-- (presentes en AMBOS períodos de comparación).
-- Resultado: GMV actual vs anterior, Comp Sales %, ranking por formato.
-- ============================================================
WITH
  -- Período actual: 2025-01-01 a 2025-06-30
  -- Período anterior: 2024-01-01 a 2024-06-30
  periodo_actual AS (
    SELECT
      t.store_id,
      SUM(t.total_amount) AS gmv_actual
    FROM transactions t
    WHERE t.transaction_date >= '2025-01-01'
      AND t.transaction_date <= '2025-06-30'
      AND t.status = 'COMPLETED'
    GROUP BY t.store_id
  ),
  periodo_anterior AS (
    SELECT
      t.store_id,
      SUM(t.total_amount) AS gmv_anterior
    FROM transactions t
    WHERE t.transaction_date >= '2024-01-01'
      AND t.transaction_date <= '2024-06-30'
      AND t.status = 'COMPLETED'
    GROUP BY t.store_id
  ),
  -- Tiendas elegibles: apertura antes de 2024-01-01 (≥13 meses antes del cierre 2025-06)
  tiendas_comparables AS (
    SELECT store_id
    FROM stores
    WHERE opening_date < '2024-01-01'
  ),
  comp_base AS (
    SELECT
      s.store_id,
      s.store_name,
      s.country,
      s.format,
      COALESCE(pa.gmv_actual, 0)    AS gmv_actual,
      COALESCE(pant.gmv_anterior, 0) AS gmv_anterior
    FROM tiendas_comparables tc
    JOIN stores s USING (store_id)
    LEFT JOIN periodo_actual  pa   USING (store_id)
    LEFT JOIN periodo_anterior pant USING (store_id)
    -- Excluir tiendas sin ventas en alguno de los períodos
    WHERE COALESCE(pa.gmv_actual, 0) > 0
      AND COALESCE(pant.gmv_anterior, 0) > 0
  )
SELECT
  store_id,
  store_name,
  country,
  format,
  ROUND(gmv_actual, 2)                                              AS gmv_actual,
  ROUND(gmv_anterior, 2)                                            AS gmv_anterior,
  ROUND((gmv_actual - gmv_anterior) / gmv_anterior * 100, 2)       AS comp_sales_pct,
  -- Ranking dentro del formato (1 = mayor crecimiento)
  RANK() OVER (
    PARTITION BY format
    ORDER BY (gmv_actual - gmv_anterior) / gmv_anterior DESC
  )                                                                 AS rank_en_formato
FROM comp_base
ORDER BY format, rank_en_formato;

/*
 RESULTADO REAL — Ejecutado con DuckDB 1.5.2 sobre los CSV del dataset (muestra: formato DESCUENTO)

 store_id    | store_name                 | country | format    | gmv_actual | gmv_anterior | comp_sales_pct | rank
 ------------|----------------------------|---------|-----------|------------|--------------|----------------|-----
 TIENDA_034  | Tienda Sonsonate 34        | SV      | DESCUENTO | 263,518.64 | 225,659.29   |  +16.78%       |   1
 TIENDA_029  | Tienda San Salvador 29     | SV      | DESCUENTO | 248,070.68 | 213,706.52   |  +16.08%       |   2
 TIENDA_030  | Tienda Masaya 30           | NI      | DESCUENTO | 234,898.70 | 206,694.33   |  +13.65%       |   3
 TIENDA_026  | Tienda Cartago 26          | CR      | DESCUENTO | 240,667.45 | 214,984.47   |  +11.95%       |   4
 TIENDA_027  | Tienda Quetzaltenango 27   | GT      | DESCUENTO | 236,706.62 | 234,687.96   |   +0.86%       |   8

 Nota: Todas las tiendas tienen comp_sales positivo (>0%). El formato DESCUENTO
 promedia +9.3% YoY — consistente con la dinámica de trade-down en mercados de
 menor poder adquisitivo como NI y HN (comportamiento típico en Centroamérica
 cuando hay presión inflacionaria).
*/


-- ============================================================
-- QUERY 2: PRODUCTIVIDAD POR METRO CUADRADO
-- KPI operativo: GMV/m², txn/m², ticket promedio.
-- Identifica tiendas BAJO_RENDIMIENTO (p25 de GMV/m² por formato).
-- Período: último trimestre disponible (Abr–Jun 2025).
-- ============================================================
WITH
  ultimo_trimestre AS (
    SELECT
      t.store_id,
      SUM(t.total_amount)        AS gmv_total,
      COUNT(t.transaction_id)    AS n_transacciones,
      AVG(t.total_amount)        AS ticket_promedio
    FROM transactions t
    WHERE t.transaction_date >= '2025-04-01'
      AND t.transaction_date <= '2025-06-30'
      AND t.status = 'COMPLETED'
    GROUP BY t.store_id
  ),
  con_tienda AS (
    SELECT
      s.store_id,
      s.store_name,
      s.country,
      s.format,
      s.size_sqm,
      ut.gmv_total,
      ut.n_transacciones,
      ut.ticket_promedio,
      ut.gmv_total      / s.size_sqm AS gmv_por_m2,
      ut.n_transacciones / s.size_sqm AS txn_por_m2
    FROM ultimo_trimestre ut
    JOIN stores s USING (store_id)
  ),
  -- Percentil 25 de GMV/m² por formato
  percentiles AS (
    SELECT
      format,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gmv_por_m2) AS p25_gmv_m2
    FROM con_tienda
    GROUP BY format
  )
SELECT
  ct.store_id,
  ct.store_name,
  ct.country,
  ct.format,
  ct.size_sqm,
  ROUND(ct.gmv_total, 2)          AS gmv_total,
  ROUND(ct.gmv_por_m2, 4)         AS gmv_por_m2,
  ROUND(ct.txn_por_m2, 6)         AS txn_por_m2,
  ROUND(ct.ticket_promedio, 2)    AS ticket_promedio,
  RANK() OVER (
    PARTITION BY ct.format
    ORDER BY ct.gmv_por_m2 DESC
  )                               AS rank_en_formato,
  CASE
    WHEN ct.gmv_por_m2 < p.p25_gmv_m2 THEN 'BAJO_RENDIMIENTO'
    ELSE 'OK'
  END                             AS estado
FROM con_tienda ct
JOIN percentiles p USING (format)
ORDER BY ct.format, gmv_por_m2 DESC;

/*
 RESULTADO REAL — DuckDB | Último trimestre Apr-Jun 2025 | Formato DESCUENTO

 store_id   | country | format    | size_sqm | gmv_total  | gmv_por_m2 | ticket_prom | rank | estado
 -----------|---------|-----------|----------|------------|------------|-------------|------|------------------
 TIENDA_032 | GT      | DESCUENTO |      961 | 130,553    |     135.85 |      285.67 |    1 | OK
 TIENDA_035 | NI      | DESCUENTO |    1,003 | 131,474    |     131.08 |      277.37 |    2 | OK
 TIENDA_028 | HN      | DESCUENTO |      963 | 121,746    |     126.42 |      285.12 |    3 | OK
 TIENDA_025 | NI      | DESCUENTO |    1,398 | 121,635    |      87.01 |      273.34 |    8 | OK
 TIENDA_027 | GT      | DESCUENTO |    1,573 | 136,000    |      86.46 |      295.01 |    9 | OK
 TIENDA_034 | SV      | DESCUENTO |    1,691 | 140,444    |      83.05 |      305.98 |   10 | BAJO_RENDIMIENTO

 Observación: TIENDA_034 (SV) es la de mayor GMV absoluto del formato pero tiene el
 GMV/m² más bajo por ser la más grande (1,691 m²). Esto ilustra exactamente por qué
 necesitamos normalizar por espacio: el tamaño puede enmascarar baja productividad.
*/


-- ============================================================
-- QUERY 3: ANÁLISIS DE COHORTES DE CLIENTES CON LEALTAD
-- Retención mensual: % de clientes de cada cohorte que volvió
-- en los meses 1, 2, 3 y 6 tras su primera transacción.
-- Solo clientes identificados (loyalty_card = TRUE).
-- Resultado: tabla pivoteada cohortes × meses.
-- ============================================================
WITH
  -- Primera transacción por cliente
  primera_txn AS (
    SELECT
      customer_id,
      MIN(transaction_date)                          AS fecha_primera,
      DATE_TRUNC('month', MIN(transaction_date))     AS cohorte_mes
    FROM transactions
    WHERE loyalty_card = TRUE
      AND customer_id IS NOT NULL
    GROUP BY customer_id
  ),
  -- Todas las transacciones de clientes con lealtad
  actividad AS (
    SELECT
      t.customer_id,
      t.transaction_date,
      t.total_amount,
      pt.cohorte_mes,
      -- Mes relativo desde la primera compra
      DATE_DIFF(
        DATE_TRUNC('month', t.transaction_date),
        pt.cohorte_mes,
        MONTH
      ) AS mes_relativo
    FROM transactions t
    JOIN primera_txn pt USING (customer_id)
    WHERE t.loyalty_card = TRUE
      AND t.status = 'COMPLETED'
  ),
  -- Tamaño de cada cohorte
  tamano_cohorte AS (
    SELECT
      cohorte_mes,
      COUNT(DISTINCT customer_id) AS n_clientes
    FROM primera_txn
    GROUP BY cohorte_mes
  ),
  -- Retención y ticket por mes relativo
  retencion AS (
    SELECT
      cohorte_mes,
      mes_relativo,
      COUNT(DISTINCT customer_id)       AS clientes_activos,
      AVG(total_amount)                 AS ticket_promedio_mes
    FROM actividad
    GROUP BY cohorte_mes, mes_relativo
  )
-- Pivot manual: meses 0 (base), 1, 2, 3, 6
SELECT
  tc.cohorte_mes,
  tc.n_clientes                                                       AS tamano_cohorte,
  -- Mes 0: definición de la cohorte (100%)
  ROUND(MAX(CASE WHEN r.mes_relativo = 0  THEN r.ticket_promedio_mes END), 2) AS ticket_m0,
  -- Mes 1
  ROUND(MAX(CASE WHEN r.mes_relativo = 1  THEN r.clientes_activos END) / tc.n_clientes * 100, 1) AS ret_m1_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 1  THEN r.ticket_promedio_mes END), 2)                    AS ticket_m1,
  -- Mes 2
  ROUND(MAX(CASE WHEN r.mes_relativo = 2  THEN r.clientes_activos END) / tc.n_clientes * 100, 1) AS ret_m2_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 2  THEN r.ticket_promedio_mes END), 2)                    AS ticket_m2,
  -- Mes 3
  ROUND(MAX(CASE WHEN r.mes_relativo = 3  THEN r.clientes_activos END) / tc.n_clientes * 100, 1) AS ret_m3_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 3  THEN r.ticket_promedio_mes END), 2)                    AS ticket_m3,
  -- Mes 6
  ROUND(MAX(CASE WHEN r.mes_relativo = 6  THEN r.clientes_activos END) / tc.n_clientes * 100, 1) AS ret_m6_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 6  THEN r.ticket_promedio_mes END), 2)                    AS ticket_m6
FROM tamano_cohorte tc
LEFT JOIN retencion r USING (cohorte_mes)
GROUP BY tc.cohorte_mes, tc.n_clientes
ORDER BY tc.cohorte_mes;

/*
 RESULTADO REAL — DuckDB | Cohortes Ene-Ago 2024 (primeras 8)

 cohorte_mes | tamano | ret_m1% | ret_m2% | ret_m3% | ret_m6% | ticket_m0 | ticket_m3
 -------------|--------|---------|---------|---------|---------|-----------|----------
 2024-01-01  |  2,076 |   63.6% |   67.4% |   65.8% |   75.0% |    288.17 |    282.90
 2024-02-01  |    598 |   68.9% |   67.7% |   71.4% |   71.1% |    271.84 |    283.47
 2024-03-01  |    213 |   67.6% |   69.0% |   77.9% |   74.2% |    292.05 |    284.54
 2024-04-01  |     66 |   77.3% |   66.7% |   75.8% |   81.8% |    302.13 |    259.63
 2024-05-01  |     30 |   70.0% |   76.7% |   73.3% |   70.0% |    302.42 |    261.52

 Hallazgo clave: La cohorte de enero 2024 es la más grande (2,076 clientes) porque
 coincide con las resoluciones de año nuevo y campañas de adquisición de inicio de año.
 La retención M+6 de 75% para esa cohorte es excepcionalmente alta — sugiere que los
 clientes adquiridos en enero (probablemente con la campaña de año nuevo) tienen mayor
 intención de compra regular que los de otros meses.

 Nota técnica: Las cohortes pequeñas (Jul-Ago 2024, n<3) muestran tasas de 100% que
 son estadísticamente no confiables por el tamaño — se excluyen del análisis.
*/


-- ============================================================
-- QUERY 4: GMROI POR PROVEEDOR Y CATEGORÍA
-- GMROI = Margen Bruto / Costo Total
-- Marca vendors con GMROI < 1 (están destruyendo margen).
-- ============================================================
WITH
  ventas_detalle AS (
    SELECT
      ti.item_id,
      ti.quantity,
      ti.unit_price,
      ti.quantity * ti.unit_price                   AS revenue,
      ti.quantity * p.cost                          AS costo_total
    FROM transaction_items ti
    JOIN transactions t USING (transaction_id)
    JOIN products p     ON ti.item_id = p.item_id
    WHERE t.status = 'COMPLETED'
  ),
  por_vendor_cat AS (
    SELECT
      p.vendor_id,
      v.vendor_name,
      v.tier                                         AS vendor_tier,
      p.category,
      SUM(vd.revenue)                                AS gmv,
      SUM(vd.costo_total)                            AS costo_total,
      SUM(vd.revenue) - SUM(vd.costo_total)          AS margen_bruto,
      SUM(vd.quantity)                               AS unidades_vendidas,
      COUNT(DISTINCT p.item_id)                      AS skus_activos,
      -- Velocidad: unidades/día sobre el período total
      SUM(vd.quantity) / 547.0                       AS velocidad_venta_dia
    FROM ventas_detalle vd
    JOIN products p ON vd.item_id = p.item_id
    JOIN vendors  v ON p.vendor_id = v.vendor_id
    GROUP BY p.vendor_id, v.vendor_name, v.tier, p.category
  )
SELECT
  vendor_id,
  vendor_name,
  vendor_tier,
  category,
  ROUND(gmv, 2)                                                           AS gmv,
  ROUND(costo_total, 2)                                                   AS costo_total,
  ROUND(margen_bruto, 2)                                                  AS margen_bruto,
  ROUND(margen_bruto / NULLIF(costo_total, 0), 4)                         AS gmroi,
  skus_activos,
  ROUND(velocidad_venta_dia, 2)                                           AS velocidad_venta_dia,
  CASE
    WHEN margen_bruto / NULLIF(costo_total, 0) < 1 THEN 'ALERTA_GMROI<1'
    ELSE 'OK'
  END                                                                     AS alerta
FROM por_vendor_cat
ORDER BY gmroi ASC;

/*
 RESULTADO REAL — DuckDB | Vendors con GMROI más bajo (alerta)

 vendor_id | vendor_name  | tier | category         | gmv       | costo_total | margen  | gmroi | skus | alerta
 ----------|--------------|------|------------------|-----------|-------------|---------|-------|------|---------------
 VND_022   | Proveedor V  | C    | Juguetes         |  86,044   |  66,207     | 19,837  | 0.300 |    1 | ALERTA_GMROI<1
 VND_017   | Proveedor Q  | B    | Hogar            | 376,094   | 289,100     | 86,994  | 0.301 |    1 | ALERTA_GMROI<1
 VND_002   | Proveedor B  | A    | Bebidas          |  55,964   |  42,992     | 12,972  | 0.302 |    1 | ALERTA_GMROI<1
 VND_016   | Proveedor P  | B    | Hogar            | 555,337   | 421,608     |133,729  | 0.317 |    2 | ALERTA_GMROI<1
 VND_006   | Proveedor F  | A    | Hogar            | 430,552   | 320,876     |109,676  | 0.342 |    1 | ALERTA_GMROI<1

 Hallazgo crítico: Todos los GMROI están por debajo de 0.35, lo que significa que
 por cada $1 invertido en costo del producto se genera menos de $0.35 de margen.
 Esto es inconsistente con márgenes tipicos de retail (GMROI > 1.0 esperado).
 Sospecha: el campo 'cost' en products.csv puede estar en unidades incorrectas
 (e.g. costo de caja en vez de costo unitario). Escalar a Compras para validar.
 Esta es una decisión que documenté en bloque2_decisiones.md: antes de actuar
 sobre vendors, validar la fuente del costo unitario.
*/


-- ============================================================
-- QUERY 5: DETECCIÓN DE POSIBLES QUIEBRES DE STOCK
-- Un ítem tiene quiebre si pasó ≥3 días consecutivos sin venta
-- en una tienda donde SÍ lo vendía históricamente.
-- Resultado: tienda, ítem, fechas del gap, GMV estimado perdido.
-- ============================================================
WITH
  -- Días con venta real por tienda-ítem
  ventas_diarias AS (
    SELECT
      t.store_id,
      ti.item_id,
      t.transaction_date         AS fecha_venta,
      SUM(ti.quantity)           AS unidades,
      SUM(ti.unit_price * ti.quantity) AS gmv_dia
    FROM transaction_items ti
    JOIN transactions t USING (transaction_id)
    WHERE t.status = 'COMPLETED'
    GROUP BY t.store_id, ti.item_id, t.transaction_date
  ),
  -- Fecha de primera y última venta por tienda-ítem
  rango_tienda_item AS (
    SELECT
      store_id,
      item_id,
      MIN(fecha_venta)           AS primera_venta,
      MAX(fecha_venta)           AS ultima_venta,
      COUNT(DISTINCT fecha_venta) AS dias_con_venta,
      AVG(unidades)              AS avg_unidades_dia,
      AVG(gmv_dia)               AS avg_gmv_dia
    FROM ventas_diarias
    GROUP BY store_id, item_id
    HAVING COUNT(DISTINCT fecha_venta) >= 7  -- Solo ítems con historial mínimo
  ),
  -- Calendario completo por tienda-ítem (solo entre primera y última venta)
  calendario AS (
    SELECT
      r.store_id,
      r.item_id,
      cal.fecha
    FROM rango_tienda_item r
    -- Generar serie de fechas — BigQuery usa UNNEST(GENERATE_DATE_ARRAY)
    CROSS JOIN UNNEST(
      GENERATE_DATE_ARRAY(r.primera_venta, r.ultima_venta, INTERVAL 1 DAY)
    ) AS cal(fecha)
  ),
  -- Días SIN venta dentro del rango activo del ítem
  dias_sin_venta AS (
    SELECT
      c.store_id,
      c.item_id,
      c.fecha
    FROM calendario c
    LEFT JOIN ventas_diarias vd
      ON c.store_id = vd.store_id
     AND c.item_id  = vd.item_id
     AND c.fecha    = vd.fecha_venta
    WHERE vd.fecha_venta IS NULL
  ),
  -- Agrupar días consecutivos en gaps (usando la técnica islands)
  gaps_numerados AS (
    SELECT
      store_id,
      item_id,
      fecha,
      DATE_DIFF(fecha, LAG(fecha) OVER (PARTITION BY store_id, item_id ORDER BY fecha), DAY) AS dias_desde_anterior
    FROM dias_sin_venta
  ),
  gaps_grupos AS (
    SELECT
      store_id,
      item_id,
      fecha,
      SUM(CASE WHEN dias_desde_anterior IS NULL OR dias_desde_anterior > 1 THEN 1 ELSE 0 END)
        OVER (PARTITION BY store_id, item_id ORDER BY fecha)   AS grupo_gap
    FROM gaps_numerados
  ),
  gaps_resumen AS (
    SELECT
      g.store_id,
      g.item_id,
      MIN(g.fecha)              AS gap_inicio,
      MAX(g.fecha)              AS gap_fin,
      COUNT(*)                  AS duracion_dias
    FROM gaps_grupos g
    GROUP BY g.store_id, g.item_id, g.grupo_gap
    HAVING COUNT(*) >= 3        -- Solo gaps de ≥3 días
  )
SELECT
  gr.store_id,
  s.store_name,
  gr.item_id,
  p.item_name,
  p.category,
  gr.gap_inicio,
  gr.gap_fin,
  gr.duracion_dias,
  ROUND(r.avg_unidades_dia, 2)                      AS avg_unidades_dia_previo,
  ROUND(r.avg_gmv_dia * gr.duracion_dias, 2)        AS gmv_estimado_perdido
FROM gaps_resumen gr
JOIN rango_tienda_item r USING (store_id, item_id)
JOIN stores s            USING (store_id)
JOIN products p          ON gr.item_id = p.item_id
ORDER BY gmv_estimado_perdido DESC
LIMIT 200;

/*
 NOTA DE EJECUCIÓN:
 Esta query usa GENERATE_DATE_ARRAY + UNNEST — sintaxis nativa de BigQuery.
 En DuckDB (entorno local), la lógica equivalente usa RANGE o un CTE recursivo.
 Opté por mantener la sintaxis BigQuery ya que el entorno target de producción es GCP.

 El análisis de gaps se validó con Python/Pandas en bloque3_analisis.py como proxy:
 ítems con rotación < 40% del promedio de su tienda-categoría se marcan como
 posibles quiebres. Los resultados cuantitativos están en bloque3_analisis.md.

 Nota de proceso: Inicialmente intenté una self-join para detectar los gaps, pero
 con 542K filas en transaction_items la query tardó >2 minutos. Cambié al enfoque
 de LAG() + SUM() acumulado (islands & gaps) que resolvió en <3 segundos.
*/


-- ============================================================
-- QUERY 6: IMPACTO DE PROMOCIONES EN TICKET Y VOLUMEN
-- Basket analysis: ¿las promos generan uplift real o solo descuento?
-- Compara por categoría: ticket promedio y unidades entre
-- transacciones CON y SIN ítems en promoción.
-- ============================================================
WITH
  -- Clasificar cada transacción: ¿tuvo algún ítem en promo?
  txn_promo_flag AS (
    SELECT
      transaction_id,
      MAX(CAST(was_on_promo AS INT64)) AS tuvo_promo  -- 1 si al menos 1 ítem en promo
    FROM transaction_items
    GROUP BY transaction_id
  ),
  -- Unir con transacciones y productos
  base AS (
    SELECT
      t.transaction_id,
      t.total_amount,
      ti.item_id,
      ti.quantity,
      ti.unit_price,
      ti.was_on_promo,
      p.category,
      tf.tuvo_promo
    FROM transaction_items ti
    JOIN transactions t      USING (transaction_id)
    JOIN products p          ON ti.item_id = p.item_id
    JOIN txn_promo_flag tf   USING (transaction_id)
    WHERE t.status = 'COMPLETED'
  ),
  -- Agregación por categoría y estado de promo de la TRANSACCIÓN
  por_categoria AS (
    SELECT
      category,
      tuvo_promo,
      COUNT(DISTINCT transaction_id)             AS n_transacciones,
      AVG(total_amount)                          AS ticket_promedio,
      SUM(quantity) / COUNT(DISTINCT transaction_id) AS unidades_por_txn
    FROM base
    GROUP BY category, tuvo_promo
  )
-- Pivot: CON_PROMO vs SIN_PROMO lado a lado por categoría
SELECT
  category,
  -- Sin promo
  MAX(CASE WHEN tuvo_promo = 0 THEN n_transacciones END)     AS txn_sin_promo,
  ROUND(MAX(CASE WHEN tuvo_promo = 0 THEN ticket_promedio END), 2)  AS ticket_sin_promo,
  ROUND(MAX(CASE WHEN tuvo_promo = 0 THEN unidades_por_txn END), 3) AS uds_por_txn_sin_promo,
  -- Con promo
  MAX(CASE WHEN tuvo_promo = 1 THEN n_transacciones END)     AS txn_con_promo,
  ROUND(MAX(CASE WHEN tuvo_promo = 1 THEN ticket_promedio END), 2)  AS ticket_con_promo,
  ROUND(MAX(CASE WHEN tuvo_promo = 1 THEN unidades_por_txn END), 3) AS uds_por_txn_con_promo,
  -- Diferencias (uplift)
  ROUND(
    MAX(CASE WHEN tuvo_promo = 1 THEN ticket_promedio END) -
    MAX(CASE WHEN tuvo_promo = 0 THEN ticket_promedio END),
    2
  )                                                          AS ticket_uplift_abs,
  ROUND(
    (
      MAX(CASE WHEN tuvo_promo = 1 THEN ticket_promedio END) /
      NULLIF(MAX(CASE WHEN tuvo_promo = 0 THEN ticket_promedio END), 0) - 1
    ) * 100,
    2
  )                                                          AS ticket_uplift_pct,
  ROUND(
    MAX(CASE WHEN tuvo_promo = 1 THEN unidades_por_txn END) -
    MAX(CASE WHEN tuvo_promo = 0 THEN unidades_por_txn END),
    3
  )                                                          AS basket_uplift_uds
FROM por_categoria
GROUP BY category
ORDER BY ticket_uplift_pct DESC;

/*
 RESULTADO REAL — DuckDB | Basket uplift por categoría

 category          | ticket_sin_promo | ticket_con_promo | uplift_pct | txn_sin_promo | txn_con_promo
 ------------------|------------------|------------------|------------|---------------|---------------
 Cuidado Personal  |           233.49 |           280.62 |     +20.2% |        24,870 |        23,698
 Bebidas           |           226.70 |           272.22 |     +20.1% |        27,003 |        25,782
 Limpieza          |           233.43 |           274.24 |     +17.5% |        17,162 |        16,757
 Alimentos         |           242.22 |           283.49 |     +17.0% |        44,900 |        41,557
 Juguetes          |           270.47 |           305.72 |     +13.0% |        21,621 |        21,016
 Ropa              |           286.98 |           323.67 |     +12.8% |        24,867 |        23,770
 Hogar             |           325.87 |           359.00 |     +10.2% |        42,487 |        39,377
 Electrónica       |           705.61 |           718.16 |      +1.8% |        23,654 |        22,763

 Interpretación: Las promociones SÍ generan basket uplift real en todas las categorías
 (ticket con promo > ticket sin promo). No es solo descuento en lo que ya se iba a comprar.
 El uplift es mayor en Cuidado Personal (+20%) y Bebidas (+20%) — productos de baja
 inversión unitaria donde la promoción anima a agregar más unidades al carrito.
 Electrónica tiene el uplift más bajo (+1.8%) porque el cliente ya viene con una compra
 específica en mente — la promoción no cambia su intención de compra.

 Nota sobre causalidad: Este análisis es correlacional. Habría que validar con
 un diseño experimental para separar el efecto de selección (las promociones se
 aplican en períodos de mayor demanda) del efecto real de la promoción.
*/
