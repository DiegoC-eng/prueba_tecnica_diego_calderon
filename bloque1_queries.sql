-- ============================================================
-- BLOQUE 1 — SQL Avanzado
-- Prueba Técnica: Data Analyst | Cadena Retail Multiformato CAM
-- Autor: Diego A. Calderón C.
-- Dataset: Enero 2024 – Junio 2025 | 40 tiendas | 5 países
-- Dialecto: BigQuery Standard SQL (compatible con SQL estándar)
-- Nota: Se asume que las tablas viven en el dataset `retail`
-- Decisiones de calidad aplicadas (ver bloque0_auditoria.md):
--   - Se excluyen transacciones con total_amount <= 0
--   - Se excluyen transacciones con store_id sin registro en stores
--   - Para Comp Sales se excluyen tiendas con < 13 meses de operación
-- ============================================================


-- ============================================================
-- QUERY 1: Ventas Comparables (Comp Sales) YoY
-- Métrica: GMV Año Actual vs Año Anterior por país y formato
-- Solo tiendas con ≥13 meses de operación (comparables)
-- ============================================================
WITH

-- Paso 1: Determinar tiendas comparables (abiertas >= 13 meses antes del periodo actual)
comparable_stores AS (
    SELECT
        store_id,
        country,
        format,
        opening_date,
        -- Una tienda es comparable si lleva al menos 13 meses abierta
        DATE_DIFF(DATE '2025-06-30', opening_date, MONTH) AS months_open
    FROM `retail.stores`
    WHERE DATE_DIFF(DATE '2025-06-30', opening_date, MONTH) >= 13
),

-- Paso 2: Ventas del año actual (Ene–Jun 2025)
current_year AS (
    SELECT
        t.store_id,
        SUM(t.total_amount) AS gmv_current
    FROM `retail.transactions` t
    INNER JOIN comparable_stores cs ON t.store_id = cs.store_id
    WHERE
        t.transaction_date BETWEEN '2025-01-01' AND '2025-06-30'
        AND t.total_amount > 0           -- excluir reversos
        AND t.status = 'COMPLETED'
    GROUP BY t.store_id
),

-- Paso 3: Ventas del año anterior (Ene–Jun 2024)
prior_year AS (
    SELECT
        t.store_id,
        SUM(t.total_amount) AS gmv_prior
    FROM `retail.transactions` t
    INNER JOIN comparable_stores cs ON t.store_id = cs.store_id
    WHERE
        t.transaction_date BETWEEN '2024-01-01' AND '2024-06-30'
        AND t.total_amount > 0
        AND t.status = 'COMPLETED'
    GROUP BY t.store_id
),

-- Paso 4: Unir y calcular crecimiento
comp_sales AS (
    SELECT
        cs.store_id,
        cs.country,
        cs.format,
        COALESCE(cy.gmv_current, 0)  AS gmv_current,
        COALESCE(py.gmv_prior, 0)    AS gmv_prior,
        -- Comp Sales Growth % = (actual - anterior) / anterior
        SAFE_DIVIDE(
            COALESCE(cy.gmv_current, 0) - COALESCE(py.gmv_prior, 0),
            COALESCE(py.gmv_prior, 0)
        ) * 100 AS comp_sales_growth_pct
    FROM comparable_stores cs
    LEFT JOIN current_year  cy ON cs.store_id = cy.store_id
    LEFT JOIN prior_year    py ON cs.store_id = py.store_id
)

-- Resultado final: ranking por formato + agregado por país y formato
SELECT
    country,
    format,
    store_id,
    ROUND(gmv_current, 2)          AS gmv_2025,
    ROUND(gmv_prior, 2)            AS gmv_2024,
    ROUND(comp_sales_growth_pct,1) AS comp_growth_pct,
    -- Ranking dentro del formato (1 = mayor crecimiento)
    RANK() OVER (
        PARTITION BY format
        ORDER BY comp_sales_growth_pct DESC
    ) AS rank_in_format
FROM comp_sales
ORDER BY format, comp_sales_growth_pct DESC;


-- ============================================================
-- QUERY 2: Productividad por Metro Cuadrado
-- KPI: GMV/m², Transacciones/m², Ticket promedio
-- Periodo: Último trimestre disponible (Abr–Jun 2025)
-- Marca BAJO_RENDIMIENTO = por debajo del P25 de GMV/m² en su formato
-- ============================================================
WITH

-- Ventas del último trimestre por tienda
last_quarter AS (
    SELECT
        t.store_id,
        SUM(t.total_amount)   AS gmv_total,
        COUNT(t.transaction_id) AS num_transactions,
        AVG(t.total_amount)   AS avg_ticket
    FROM `retail.transactions` t
    WHERE
        t.transaction_date BETWEEN '2025-04-01' AND '2025-06-30'
        AND t.total_amount > 0
        AND t.status = 'COMPLETED'
    GROUP BY t.store_id
),

-- KPIs por m²
productivity AS (
    SELECT
        lq.store_id,
        s.country,
        s.format,
        s.size_sqm,
        ROUND(lq.gmv_total, 2)                             AS gmv_last_quarter,
        ROUND(lq.gmv_total    / s.size_sqm, 2)             AS gmv_per_sqm,
        ROUND(lq.num_transactions / s.size_sqm, 4)         AS tx_per_sqm,
        ROUND(lq.avg_ticket, 2)                            AS avg_ticket
    FROM last_quarter lq
    INNER JOIN `retail.stores` s ON lq.store_id = s.store_id
),

-- Percentil 25 de GMV/m² por formato
format_p25 AS (
    SELECT
        format,
        PERCENTILE_CONT(gmv_per_sqm, 0.25) OVER (PARTITION BY format) AS p25_gmv_sqm
    FROM productivity
)

SELECT
    p.store_id,
    p.country,
    p.format,
    p.size_sqm,
    p.gmv_last_quarter,
    p.gmv_per_sqm,
    p.tx_per_sqm,
    p.avg_ticket,
    -- Ranking dentro del formato (1 = mejor productividad)
    RANK() OVER (PARTITION BY p.format ORDER BY p.gmv_per_sqm DESC) AS rank_in_format,
    -- Etiqueta de bajo rendimiento
    CASE
        WHEN p.gmv_per_sqm < fp.p25_gmv_sqm THEN 'BAJO_RENDIMIENTO'
        ELSE 'NORMAL'
    END AS performance_flag
FROM productivity p
INNER JOIN format_p25 fp ON p.format = fp.format
ORDER BY p.format, p.gmv_per_sqm DESC;


-- ============================================================
-- QUERY 3: Cohortes de Clientes con Tarjeta de Lealtad
-- Cohorte = mes de primera transacción del cliente
-- Retención en meses 1, 2, 3 y 6 post-adquisición
-- Resultado: tabla pivoteada (cohortes en filas, meses en columnas)
-- ============================================================
WITH

-- Solo clientes con tarjeta de lealtad identificados
loyalty_tx AS (
    SELECT
        customer_id,
        transaction_id,
        transaction_date,
        total_amount
    FROM `retail.transactions`
    WHERE
        loyalty_card = TRUE
        AND customer_id IS NOT NULL
        AND total_amount > 0
        AND status = 'COMPLETED'
),

-- Mes de primera transacción = cohorte del cliente
first_tx AS (
    SELECT
        customer_id,
        DATE_TRUNC(MIN(transaction_date), MONTH) AS cohort_month
    FROM loyalty_tx
    GROUP BY customer_id
),

-- Combinar: para cada transacción, calcular cuantos meses después de la cohorte ocurrió
cohort_activity AS (
    SELECT
        f.cohort_month,
        lt.customer_id,
        lt.transaction_id,
        lt.total_amount,
        DATE_DIFF(
            DATE_TRUNC(lt.transaction_date, MONTH),
            f.cohort_month,
            MONTH
        ) AS months_since_cohort
    FROM loyalty_tx lt
    INNER JOIN first_tx f ON lt.customer_id = f.customer_id
),

-- Tamaño de cohorte (clientes únicos por mes de primera compra)
cohort_size AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS cohort_size
    FROM first_tx
    GROUP BY cohort_month
),

-- Retención y ticket promedio por cohorte y mes
retention_base AS (
    SELECT
        cohort_month,
        months_since_cohort,
        COUNT(DISTINCT customer_id) AS retained_customers,
        AVG(total_amount)           AS avg_ticket
    FROM cohort_activity
    GROUP BY cohort_month, months_since_cohort
)

-- Tabla pivoteada: retencion en meses 0, 1, 2, 3 y 6
SELECT
    rb.cohort_month,
    cs.cohort_size,
    -- Mes 0 = mes de adquisición (debe ser 100%)
    ROUND(MAX(CASE WHEN months_since_cohort = 0
        THEN retained_customers / cs.cohort_size * 100 END), 1) AS ret_m0_pct,
    -- Mes 1
    ROUND(MAX(CASE WHEN months_since_cohort = 1
        THEN retained_customers / cs.cohort_size * 100 END), 1) AS ret_m1_pct,
    -- Mes 2
    ROUND(MAX(CASE WHEN months_since_cohort = 2
        THEN retained_customers / cs.cohort_size * 100 END), 1) AS ret_m2_pct,
    -- Mes 3
    ROUND(MAX(CASE WHEN months_since_cohort = 3
        THEN retained_customers / cs.cohort_size * 100 END), 1) AS ret_m3_pct,
    -- Mes 6
    ROUND(MAX(CASE WHEN months_since_cohort = 6
        THEN retained_customers / cs.cohort_size * 100 END), 1) AS ret_m6_pct,
    -- Ticket promedio en mes 0 vs mes 6 (crecimiento del ticket retenido)
    ROUND(MAX(CASE WHEN months_since_cohort = 0
        THEN avg_ticket END), 2)  AS ticket_m0,
    ROUND(MAX(CASE WHEN months_since_cohort = 6
        THEN avg_ticket END), 2)  AS ticket_m6
FROM retention_base rb
INNER JOIN cohort_size cs ON rb.cohort_month = cs.cohort_month
GROUP BY rb.cohort_month, cs.cohort_size
ORDER BY rb.cohort_month;


-- ============================================================
-- QUERY 4: GMROI por Proveedor y Categoría
-- GMROI = Margen Bruto / Costo Total
-- Marca vendors con GMROI < 1 (generan menos margen que lo que cuestan)
-- ============================================================
WITH

-- Ventas con información de producto (join items -> productos -> vendors)
sales_with_cost AS (
    SELECT
        ti.transaction_id,
        ti.item_id,
        ti.quantity,
        ti.unit_price,
        p.vendor_id,
        p.category,
        p.cost                              AS unit_cost,
        ti.quantity * ti.unit_price         AS line_gmv,
        ti.quantity * p.cost                AS line_cost
    FROM `retail.transaction_items` ti
    INNER JOIN `retail.products` p ON ti.item_id = p.item_id
    -- Excluir items con precio 0 sin promo (datos anomalos, ver bloque0)
    WHERE NOT (ti.unit_price = 0 AND ti.was_on_promo = FALSE)
),

-- Agregar por vendor + categoría
gmroi_base AS (
    SELECT
        s.vendor_id,
        v.vendor_name,
        s.category,
        SUM(s.line_gmv)                     AS gmv_total,
        SUM(s.line_cost)                    AS cost_total,
        SUM(s.line_gmv) - SUM(s.line_cost)  AS gross_margin,
        COUNT(DISTINCT s.item_id)           AS active_skus,
        -- Velocidad de venta: unidades vendidas / días del periodo
        SUM(s.quantity) / 547.0             AS units_per_day  -- Jan2024-Jun2025 = ~547 días
    FROM sales_with_cost s
    INNER JOIN `retail.vendors` v ON s.vendor_id = v.vendor_id
    GROUP BY s.vendor_id, v.vendor_name, s.category
)

SELECT
    vendor_id,
    vendor_name,
    category,
    ROUND(gmv_total, 2)       AS gmv_total,
    ROUND(cost_total, 2)      AS cost_total,
    ROUND(gross_margin, 2)    AS gross_margin,
    ROUND(gross_margin / NULLIF(cost_total, 0), 4)  AS gmroi,
    active_skus,
    ROUND(units_per_day, 2)   AS units_per_day,
    -- Flag de bajo rendimiento
    CASE
        WHEN SAFE_DIVIDE(gross_margin, cost_total) < 1
        THEN 'GMROI_BAJO'
        ELSE 'OK'
    END AS gmroi_flag
FROM gmroi_base
ORDER BY gmroi ASC;  -- Peores primero (los que necesitan atención)


-- ============================================================
-- QUERY 5: Detección de Posibles Quiebres de Stock
-- Un ítem tiene quiebre si pasó >= 3 días consecutivos SIN vender
-- en una tienda donde históricamente sí lo vendía.
-- GMV estimado perdido = ventas promedio diarias * días de gap
-- ============================================================
WITH

-- Paso 1: Obtener todos los días de venta por tienda-item
item_sales_days AS (
    SELECT DISTINCT
        t.store_id,
        ti.item_id,
        DATE(t.transaction_date) AS sale_date
    FROM `retail.transaction_items` ti
    INNER JOIN `retail.transactions` t ON ti.transaction_id = t.transaction_id
    WHERE t.total_amount > 0 AND t.status = 'COMPLETED'
),

-- Paso 2: Para cada tienda-item, generar el calendario de días que debería haber vendido
-- (desde primer venta hasta última venta de ese item en esa tienda)
item_date_range AS (
    SELECT
        store_id,
        item_id,
        MIN(sale_date) AS first_sale,
        MAX(sale_date) AS last_sale
    FROM item_sales_days
    GROUP BY store_id, item_id
    -- Solo items con al menos 10 días de venta histórica (relevantes)
    HAVING COUNT(DISTINCT sale_date) >= 10
),

-- Paso 3: Calcular ventas promedio diarias por tienda-item (antes del gap)
daily_avg_sales AS (
    SELECT
        t.store_id,
        ti.item_id,
        SUM(ti.unit_price * ti.quantity) / COUNT(DISTINCT DATE(t.transaction_date)) AS avg_daily_gmv
    FROM `retail.transaction_items` ti
    INNER JOIN `retail.transactions` t ON ti.transaction_id = t.transaction_id
    WHERE t.total_amount > 0 AND t.status = 'COMPLETED'
    GROUP BY t.store_id, ti.item_id
),

-- Paso 4: Detectar gaps usando LAG — diferencia de días entre ventas consecutivas
gaps AS (
    SELECT
        store_id,
        item_id,
        sale_date,
        LAG(sale_date) OVER (PARTITION BY store_id, item_id ORDER BY sale_date) AS prev_sale_date,
        DATE_DIFF(
            sale_date,
            LAG(sale_date) OVER (PARTITION BY store_id, item_id ORDER BY sale_date),
            DAY
        ) - 1 AS gap_days  -- días sin venta entre dos ventas consecutivas
    FROM item_sales_days
),

-- Paso 5: Filtrar solo gaps >= 3 días (definición de quiebre)
significant_gaps AS (
    SELECT
        g.store_id,
        g.item_id,
        g.prev_sale_date  AS gap_start,
        g.sale_date       AS gap_end,
        g.gap_days
    FROM gaps g
    INNER JOIN item_date_range idr ON g.store_id = idr.store_id AND g.item_id = idr.item_id
    WHERE g.gap_days >= 3
)

-- Resultado final con GMV estimado perdido
SELECT
    sg.store_id,
    sg.item_id,
    p.category,
    p.item_name,
    sg.gap_start,
    sg.gap_end,
    sg.gap_days,
    ROUND(das.avg_daily_gmv, 2)                        AS avg_daily_gmv_before_gap,
    ROUND(das.avg_daily_gmv * sg.gap_days, 2)          AS estimated_lost_gmv
FROM significant_gaps sg
INNER JOIN daily_avg_sales    das ON sg.store_id = das.store_id AND sg.item_id = das.item_id
INNER JOIN `retail.products`  p   ON sg.item_id  = p.item_id
ORDER BY estimated_lost_gmv DESC;  -- Mayor impacto primero


-- ============================================================
-- QUERY 6: Impacto de Promociones en Ticket y Volumen
-- Basket analysis: ¿Las promos generan uplift o solo descuento?
-- Compara transacciones CON vs SIN ítems en promo por categoría
-- ============================================================
WITH

-- Clasificar transacciones: ¿tiene al menos un ítem en promo?
transaction_promo_flag AS (
    SELECT
        transaction_id,
        -- TRUE si al menos un item de la transaccion estaba en promo
        MAX(CASE WHEN was_on_promo = TRUE THEN 1 ELSE 0 END) AS has_promo_item,
        -- Número de unidades totales por transacción
        SUM(quantity)  AS total_units,
        COUNT(item_id) AS distinct_skus
    FROM `retail.transaction_items`
    GROUP BY transaction_id
),

-- Join con transacciones y agregar por categoría
category_basket AS (
    SELECT
        p.category,
        tpf.has_promo_item,
        t.total_amount,
        tpf.total_units,
        tpf.distinct_skus
    FROM transaction_promo_flag tpf
    INNER JOIN `retail.transactions` t ON tpf.transaction_id = t.transaction_id
    -- Join con items para obtener la categoría dominante de la transacción
    INNER JOIN (
        -- Categoría con más GMV en la transacción
        SELECT
            ti.transaction_id,
            p2.category,
            ROW_NUMBER() OVER (
                PARTITION BY ti.transaction_id
                ORDER BY SUM(ti.unit_price * ti.quantity) DESC
            ) AS rn
        FROM `retail.transaction_items` ti
        INNER JOIN `retail.products` p2 ON ti.item_id = p2.item_id
        GROUP BY ti.transaction_id, p2.category
    ) cat ON tpf.transaction_id = cat.transaction_id AND cat.rn = 1
    INNER JOIN `retail.products` p ON p.category = cat.category
    WHERE t.total_amount > 0 AND t.status = 'COMPLETED'
)

-- Comparativa CON vs SIN promo por categoría
SELECT
    category,
    CASE WHEN has_promo_item = 1 THEN 'CON_PROMO' ELSE 'SIN_PROMO' END AS promo_group,
    COUNT(*)                          AS num_transactions,
    ROUND(AVG(total_amount), 2)       AS avg_ticket,
    ROUND(AVG(total_units), 2)        AS avg_units_per_tx,
    ROUND(AVG(distinct_skus), 2)      AS avg_skus_per_tx,
    -- Uplift de ticket vs sin promo (se calcula al comparar filas)
    -- Si avg_ticket CON_PROMO > SIN_PROMO => basket uplift real
    -- Si avg_ticket CON_PROMO <= SIN_PROMO => solo descuento en lo mismo
    ROUND(
        AVG(total_amount) - AVG(AVG(total_amount)) OVER (PARTITION BY category),
        2
    ) AS ticket_vs_category_avg
FROM category_basket
GROUP BY category, has_promo_item
ORDER BY category, has_promo_item DESC;
