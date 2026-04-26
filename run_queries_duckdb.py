"""
Corre las queries del bloque1 contra los CSVs reales usando DuckDB.
Guarda los resultados para insertar en el .sql como evidencia.
"""
import duckdb
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

DATA = r'C:\Users\d0c00v5\Downloads\Datasets_extracted'

con = duckdb.connect()

# Cargar tablas
print('Cargando tablas...')
con.execute(f"CREATE OR REPLACE VIEW transactions AS SELECT * FROM read_csv_auto('{DATA}/transactions.csv')")
con.execute(f"CREATE OR REPLACE VIEW transaction_items AS SELECT * FROM read_csv_auto('{DATA}/transaction_items.csv')")
con.execute(f"CREATE OR REPLACE VIEW stores AS SELECT * FROM read_csv_auto('{DATA}/stores.csv')")
con.execute(f"CREATE OR REPLACE VIEW products AS SELECT * FROM read_csv_auto('{DATA}/products.csv')")
con.execute(f"CREATE OR REPLACE VIEW vendors AS SELECT * FROM read_csv_auto('{DATA}/vendors.csv')")
con.execute(f"CREATE OR REPLACE VIEW store_promotions AS SELECT * FROM read_csv_auto('{DATA}/store_promotions.csv')")
print('Tablas listas.\n')

results = {}

# ------------------------------------------------------------------
# QUERY 1 — COMP SALES
# ------------------------------------------------------------------
print('Corriendo Q1 - Comp Sales...')
q1 = """
WITH
  periodo_actual AS (
    SELECT store_id, SUM(total_amount) AS gmv_actual
    FROM transactions
    WHERE transaction_date >= '2025-01-01' AND transaction_date <= '2025-06-30'
      AND status = 'COMPLETED'
    GROUP BY store_id
  ),
  periodo_anterior AS (
    SELECT store_id, SUM(total_amount) AS gmv_anterior
    FROM transactions
    WHERE transaction_date >= '2024-01-01' AND transaction_date <= '2024-06-30'
      AND status = 'COMPLETED'
    GROUP BY store_id
  ),
  tiendas_comparables AS (
    SELECT store_id FROM stores WHERE opening_date < '2024-01-01'
  ),
  comp_base AS (
    SELECT
      s.store_id, s.store_name, s.country, s.format,
      COALESCE(pa.gmv_actual, 0) AS gmv_actual,
      COALESCE(pant.gmv_anterior, 0) AS gmv_anterior
    FROM tiendas_comparables tc
    JOIN stores s USING (store_id)
    LEFT JOIN periodo_actual pa USING (store_id)
    LEFT JOIN periodo_anterior pant USING (store_id)
    WHERE COALESCE(pa.gmv_actual, 0) > 0 AND COALESCE(pant.gmv_anterior, 0) > 0
  )
SELECT
  store_id, store_name, country, format,
  ROUND(gmv_actual, 2) AS gmv_actual,
  ROUND(gmv_anterior, 2) AS gmv_anterior,
  ROUND((gmv_actual - gmv_anterior) / gmv_anterior * 100, 2) AS comp_sales_pct,
  RANK() OVER (PARTITION BY format ORDER BY (gmv_actual - gmv_anterior) / gmv_anterior DESC) AS rank_en_formato
FROM comp_base
ORDER BY format, rank_en_formato
LIMIT 8
"""
df1 = con.execute(q1).df()
results['q1'] = df1
print(df1.to_string(index=False))
print()

# ------------------------------------------------------------------
# QUERY 2 — GMV/m²
# ------------------------------------------------------------------
print('Corriendo Q2 - Productividad m²...')
q2 = """
WITH
  ultimo_trimestre AS (
    SELECT store_id, SUM(total_amount) AS gmv_total,
           COUNT(transaction_id) AS n_transacciones,
           AVG(total_amount) AS ticket_promedio
    FROM transactions
    WHERE transaction_date >= '2025-04-01' AND transaction_date <= '2025-06-30'
      AND status = 'COMPLETED'
    GROUP BY store_id
  ),
  con_tienda AS (
    SELECT s.store_id, s.store_name, s.country, s.format, s.size_sqm,
           ut.gmv_total, ut.n_transacciones, ut.ticket_promedio,
           ut.gmv_total / s.size_sqm AS gmv_por_m2,
           ut.n_transacciones / s.size_sqm AS txn_por_m2
    FROM ultimo_trimestre ut JOIN stores s USING (store_id)
  ),
  percentiles AS (
    SELECT format,
           PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gmv_por_m2) AS p25_gmv_m2
    FROM con_tienda GROUP BY format
  )
SELECT
  ct.store_id, ct.country, ct.format, ct.size_sqm,
  ROUND(ct.gmv_total, 0) AS gmv_total,
  ROUND(ct.gmv_por_m2, 2) AS gmv_por_m2,
  ROUND(ct.ticket_promedio, 2) AS ticket_promedio,
  RANK() OVER (PARTITION BY ct.format ORDER BY ct.gmv_por_m2 DESC) AS rank_formato,
  CASE WHEN ct.gmv_por_m2 < p.p25_gmv_m2 THEN 'BAJO_RENDIMIENTO' ELSE 'OK' END AS estado
FROM con_tienda ct JOIN percentiles p USING (format)
ORDER BY ct.format, gmv_por_m2 DESC
LIMIT 10
"""
df2 = con.execute(q2).df()
results['q2'] = df2
print(df2.to_string(index=False))
print()

# ------------------------------------------------------------------
# QUERY 3 — COHORTES
# ------------------------------------------------------------------
print('Corriendo Q3 - Cohortes...')
q3 = """
WITH
  primera_txn AS (
    SELECT customer_id,
           MIN(transaction_date) AS fecha_primera,
           DATE_TRUNC('month', MIN(transaction_date)) AS cohorte_mes
    FROM transactions
    WHERE loyalty_card = TRUE AND customer_id IS NOT NULL
    GROUP BY customer_id
  ),
  actividad AS (
    SELECT t.customer_id, t.transaction_date, t.total_amount,
           pt.cohorte_mes,
           DATEDIFF('month', pt.cohorte_mes, DATE_TRUNC('month', t.transaction_date)) AS mes_relativo
    FROM transactions t
    JOIN primera_txn pt USING (customer_id)
    WHERE t.loyalty_card = TRUE AND t.status = 'COMPLETED'
  ),
  tamano_cohorte AS (
    SELECT cohorte_mes, COUNT(DISTINCT customer_id) AS n_clientes
    FROM primera_txn GROUP BY cohorte_mes
  ),
  retencion AS (
    SELECT cohorte_mes, mes_relativo,
           COUNT(DISTINCT customer_id) AS clientes_activos,
           AVG(total_amount) AS ticket_promedio_mes
    FROM actividad GROUP BY cohorte_mes, mes_relativo
  )
SELECT
  tc.cohorte_mes,
  tc.n_clientes AS tamano_cohorte,
  ROUND(MAX(CASE WHEN r.mes_relativo = 1 THEN r.clientes_activos END) * 100.0 / tc.n_clientes, 1) AS ret_m1_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 2 THEN r.clientes_activos END) * 100.0 / tc.n_clientes, 1) AS ret_m2_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 3 THEN r.clientes_activos END) * 100.0 / tc.n_clientes, 1) AS ret_m3_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 6 THEN r.clientes_activos END) * 100.0 / tc.n_clientes, 1) AS ret_m6_pct,
  ROUND(MAX(CASE WHEN r.mes_relativo = 0 THEN r.ticket_promedio_mes END), 2) AS ticket_m0,
  ROUND(MAX(CASE WHEN r.mes_relativo = 3 THEN r.ticket_promedio_mes END), 2) AS ticket_m3
FROM tamano_cohorte tc
LEFT JOIN retencion r USING (cohorte_mes)
GROUP BY tc.cohorte_mes, tc.n_clientes
ORDER BY tc.cohorte_mes
LIMIT 8
"""
df3 = con.execute(q3).df()
results['q3'] = df3
print(df3.to_string(index=False))
print()

# ------------------------------------------------------------------
# QUERY 4 — GMROI
# ------------------------------------------------------------------
print('Corriendo Q4 - GMROI...')
q4 = """
WITH ventas_detalle AS (
  SELECT ti.item_id, ti.quantity, ti.unit_price,
         ti.quantity * ti.unit_price AS revenue,
         ti.quantity * p.cost AS costo_total
  FROM transaction_items ti
  JOIN transactions t USING (transaction_id)
  JOIN products p ON ti.item_id = p.item_id
  WHERE t.status = 'COMPLETED'
)
SELECT
  p.vendor_id, v.vendor_name, v.tier AS vendor_tier, p.category,
  ROUND(SUM(vd.revenue), 0) AS gmv,
  ROUND(SUM(vd.costo_total), 0) AS costo_total,
  ROUND(SUM(vd.revenue) - SUM(vd.costo_total), 0) AS margen_bruto,
  ROUND((SUM(vd.revenue) - SUM(vd.costo_total)) / NULLIF(SUM(vd.costo_total), 0), 3) AS gmroi,
  COUNT(DISTINCT p.item_id) AS skus_activos,
  CASE WHEN (SUM(vd.revenue) - SUM(vd.costo_total)) / NULLIF(SUM(vd.costo_total), 0) < 1
       THEN 'ALERTA_GMROI<1' ELSE 'OK' END AS alerta
FROM ventas_detalle vd
JOIN products p ON vd.item_id = p.item_id
JOIN vendors v ON p.vendor_id = v.vendor_id
GROUP BY p.vendor_id, v.vendor_name, v.tier, p.category
ORDER BY gmroi ASC
LIMIT 8
"""
df4 = con.execute(q4).df()
results['q4'] = df4
print(df4.to_string(index=False))
print()

# ------------------------------------------------------------------
# QUERY 6 — BASKET UPLIFT (más simple, Q5 es muy lenta en DuckDB puro)
# ------------------------------------------------------------------
print('Corriendo Q6 - Basket Uplift...')
q6 = """
WITH
  txn_promo_flag AS (
    SELECT transaction_id,
           MAX(CAST(was_on_promo AS INT)) AS tuvo_promo
    FROM transaction_items GROUP BY transaction_id
  ),
  base AS (
    SELECT t.transaction_id, t.total_amount, ti.quantity, p.category, tf.tuvo_promo
    FROM transaction_items ti
    JOIN transactions t USING (transaction_id)
    JOIN products p ON ti.item_id = p.item_id
    JOIN txn_promo_flag tf USING (transaction_id)
    WHERE t.status = 'COMPLETED'
  )
SELECT
  category,
  ROUND(AVG(CASE WHEN tuvo_promo = 0 THEN total_amount END), 2) AS ticket_sin_promo,
  ROUND(AVG(CASE WHEN tuvo_promo = 1 THEN total_amount END), 2) AS ticket_con_promo,
  ROUND(
    AVG(CASE WHEN tuvo_promo = 1 THEN total_amount END) /
    NULLIF(AVG(CASE WHEN tuvo_promo = 0 THEN total_amount END), 0) * 100 - 100
  , 2) AS ticket_uplift_pct,
  COUNT(DISTINCT CASE WHEN tuvo_promo = 0 THEN transaction_id END) AS txn_sin_promo,
  COUNT(DISTINCT CASE WHEN tuvo_promo = 1 THEN transaction_id END) AS txn_con_promo
FROM base
GROUP BY category
ORDER BY ticket_uplift_pct DESC
"""
df6 = con.execute(q6).df()
results['q6'] = df6
print(df6.to_string(index=False))
print()

# Guardar como JSON para usar en el notebook
import json
output = {}
for k, df in results.items():
    output[k] = df.to_dict(orient='records')

with open('query_results.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)
print('Resultados guardados en query_results.json')
