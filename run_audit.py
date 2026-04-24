import duckdb

con = duckdb.connect()
PATH = r'C:/Users/d0c00v5/Downloads/Datasets_extracted'

con.execute(f"CREATE VIEW stores       AS SELECT * FROM read_csv_auto('{PATH}/stores.csv')")
con.execute(f"CREATE VIEW products     AS SELECT * FROM read_csv_auto('{PATH}/products.csv')")
con.execute(f"CREATE VIEW vendors      AS SELECT * FROM read_csv_auto('{PATH}/vendors.csv')")
con.execute(f"CREATE VIEW promotions   AS SELECT * FROM read_csv_auto('{PATH}/store_promotions.csv')")
con.execute(f"CREATE VIEW transactions AS SELECT * FROM read_csv_auto('{PATH}/transactions.csv')")
con.execute(f"CREATE VIEW tx_items     AS SELECT * FROM read_csv_auto('{PATH}/transaction_items.csv')")

print('\n=== Q1: COMPLETITUD ===')
r = con.execute('''
SELECT COUNT(*) AS total,
  COUNT(*) FILTER (WHERE customer_id IS NULL) AS sin_customer_id,
  ROUND(COUNT(*) FILTER (WHERE customer_id IS NULL)*100.0/COUNT(*),1) AS pct_sin_customer,
  COUNT(*) FILTER (WHERE loyalty_card = false) AS loyalty_false,
  COUNT(*) FILTER (WHERE loyalty_card = true)  AS loyalty_true,
  ROUND(COUNT(*) FILTER (WHERE loyalty_card = true)*100.0/COUNT(*),1) AS pct_con_lealtad
FROM transactions
''').df()
print(r.to_string(index=False))

print('\n=== Q2: CONSISTENCIA ===')
r = con.execute('''
WITH suma_items AS (
  SELECT transaction_id, SUM(unit_price * quantity) AS suma_calculada
  FROM tx_items GROUP BY transaction_id
)
SELECT
  COUNT(*) AS transacciones_comparadas,
  COUNT(*) FILTER (WHERE ABS(t.total_amount - s.suma_calculada) > 0.02) AS con_discrepancia,
  ROUND(COUNT(*) FILTER (WHERE ABS(t.total_amount - s.suma_calculada) > 0.02)*100.0/COUNT(*),2) AS pct_discrepancia,
  ROUND(MAX(ABS(t.total_amount - s.suma_calculada)), 2) AS diferencia_maxima
FROM transactions t
JOIN suma_items s USING (transaction_id)
''').df()
print(r.to_string(index=False))

print('\n=== Q3: UNICIDAD ===')
r = con.execute('''
SELECT 'transactions' AS tabla, COUNT(*) AS total_filas,
  COUNT(DISTINCT transaction_id) AS ids_unicos,
  COUNT(*) - COUNT(DISTINCT transaction_id) AS duplicados
FROM transactions
UNION ALL
SELECT 'transaction_items', COUNT(*),
  COUNT(DISTINCT transaction_item_id),
  COUNT(*) - COUNT(DISTINCT transaction_item_id)
FROM tx_items
''').df()
print(r.to_string(index=False))

print('\n=== Q4A: VALIDEZ - MONTOS ===')
r = con.execute('''
SELECT
  COUNT(*) FILTER (WHERE total_amount <= 0) AS montos_invalidos,
  COUNT(*) FILTER (WHERE total_amount < 0)  AS montos_negativos,
  COUNT(*) FILTER (WHERE total_amount = 0)  AS montos_cero,
  ROUND(MIN(total_amount), 2) AS monto_minimo,
  ROUND(MAX(total_amount), 2) AS monto_maximo,
  ROUND(AVG(total_amount), 2) AS monto_promedio
FROM transactions
''').df()
print(r.to_string(index=False))

print('\n=== Q4B: VALIDEZ - PRECIOS ===')
r = con.execute('''
SELECT
  COUNT(*) FILTER (WHERE unit_price = 0) AS precio_cero_total,
  COUNT(*) FILTER (WHERE unit_price = 0 AND was_on_promo = false) AS precio_cero_sin_promo,
  COUNT(*) FILTER (WHERE unit_price = 0 AND was_on_promo = true)  AS precio_cero_con_promo,
  ROUND(COUNT(*) FILTER (WHERE unit_price = 0)*100.0/COUNT(*),2) AS pct_precio_cero
FROM tx_items
''').df()
print(r.to_string(index=False))

print('\n=== Q5A: INTEGRIDAD REF - TIENDAS ===')
r = con.execute('''
SELECT t.store_id, COUNT(*) AS transacciones_huerfanas
FROM transactions t
LEFT JOIN stores s USING (store_id)
WHERE s.store_id IS NULL
GROUP BY t.store_id
''').df()
print(r.to_string(index=False) if len(r) > 0 else 'OK - 0 tiendas huerfanas')

print('\n=== Q5B: INTEGRIDAD REF - VENDORS ===')
r = con.execute('''
SELECT p.vendor_id, COUNT(*) AS productos_afectados
FROM products p
LEFT JOIN vendors v USING (vendor_id)
WHERE v.vendor_id IS NULL
GROUP BY p.vendor_id
''').df()
print(r.to_string(index=False) if len(r) > 0 else 'OK - 0 vendors huerfanos')

print('\n=== Q6: FRESCURA - GAPS ===')
r = con.execute('''
WITH dias_venta AS (
  SELECT DISTINCT store_id, CAST(transaction_date AS DATE) AS fecha_venta
  FROM transactions
),
con_lag AS (
  SELECT store_id, fecha_venta,
    LAG(fecha_venta) OVER (PARTITION BY store_id ORDER BY fecha_venta) AS venta_anterior,
    DATEDIFF('day',
      LAG(fecha_venta) OVER (PARTITION BY store_id ORDER BY fecha_venta),
      fecha_venta
    ) - 1 AS dias_sin_ventas
  FROM dias_venta
)
SELECT store_id, venta_anterior AS gap_inicio, fecha_venta AS gap_fin,
  dias_sin_ventas,
  CASE
    WHEN dias_sin_ventas BETWEEN 3 AND 7  THEN 'REVISAR'
    WHEN dias_sin_ventas BETWEEN 8 AND 14 THEN 'ALERTA'
    WHEN dias_sin_ventas > 14             THEN 'CRITICO'
  END AS severidad
FROM con_lag
WHERE dias_sin_ventas >= 3
ORDER BY dias_sin_ventas DESC
''').df()
print(r.to_string(index=False) if len(r) > 0 else 'OK - 0 gaps detectados')

print('\n=== Q7: INTEGRIDAD TEMPORAL ===')
r = con.execute('''
SELECT t.store_id,
  CAST(s.opening_date AS DATE) AS fecha_apertura,
  MIN(CAST(t.transaction_date AS DATE)) AS primera_transaccion,
  COUNT(*) AS tx_antes_apertura
FROM transactions t
JOIN stores s USING (store_id)
WHERE CAST(t.transaction_date AS DATE) < CAST(s.opening_date AS DATE)
GROUP BY t.store_id, s.opening_date
ORDER BY tx_antes_apertura DESC
''').df()
print(r.to_string(index=False) if len(r) > 0 else 'OK - 0 transacciones antes de apertura')

print('\n=== Q8: A/B TEST ===')
r = con.execute('''
WITH variantes AS (
  SELECT store_id, promo_name,
    COUNT(DISTINCT variant) AS num_grupos,
    STRING_AGG(DISTINCT variant, ' + ') AS grupos_asignados
  FROM promotions
  GROUP BY store_id, promo_name
)
SELECT store_id, promo_name, grupos_asignados, num_grupos,
  'EXCLUIR DEL TEST' AS decision
FROM variantes WHERE num_grupos > 1
ORDER BY store_id
''').df()
print(r.to_string(index=False) if len(r) > 0 else 'OK - 0 tiendas contaminadas')

print('\n=== Q8B: RESUMEN GRUPOS A/B (sin contaminadas) ===')
r = con.execute('''
SELECT variant, COUNT(DISTINCT store_id) AS tiendas_validas
FROM promotions
WHERE store_id NOT IN (
  SELECT store_id FROM promotions
  GROUP BY store_id, promo_name
  HAVING COUNT(DISTINCT variant) > 1
)
GROUP BY variant
''').df()
print(r.to_string(index=False))

print('\n=== AUDITORIA COMPLETA ===')