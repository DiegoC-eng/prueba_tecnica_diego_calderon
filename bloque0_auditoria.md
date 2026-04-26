# Bloque 0 — Auditoría de Calidad de Datos

**Autor:** Diego Alberto Calderón Calderón  
**Dataset:** Cadena Retail Multiformato Centroamérica — Ene 2024 – Jun 2025  
**Herramienta:** Python 3.13 + Pandas 3.0  
**Fecha de análisis:** Abril 2026  

---

## Resumen del Dataset

| Archivo | Filas | Descripción |
|---|---|---|
| `transactions.csv` | 174,880 | Transacciones maestro |
| `transaction_items.csv` | 542,015 | Líneas de detalle |
| `stores.csv` | 40 | Tiendas (8 por país) |
| `products.csv` | 200 | Catálogo de productos |
| `vendors.csv` | 30 | Proveedores |
| `store_promotions.csv` | 42 | Asignaciones A/B |

**GMV total:** $48,719,262  
**Período:** 2024-01-01 a 2025-06-30 (547 días)  
**Países:** CR, GT, HN, NI, SV (8 tiendas c/u)  
**Formatos:** HIPERMERCADO (8), SUPERMERCADO (15), DESCUENTO (12), EXPRESS (5)  

---

## 1. Completitud — `customer_id`

**Pregunta:** ¿Qué % de transacciones no tiene `customer_id`? ¿Es consistente con `loyalty_card = FALSE`?

| Métrica | Valor |
|---|---|
| Transacciones sin `customer_id` | 104,632 (59.83%) |
| Transacciones con `loyalty_card = FALSE` | 104,632 |
| Diferencia | **0** |

**Hallazgo:** La ausencia de `customer_id` es 100% consistente con `loyalty_card = FALSE`. No hay registros ambiguos. Esto confirma que el campo nulo es **intencional y esperado** (clientes sin tarjeta de lealtad).  
**Decisión:** Sin acción correctiva. Los análisis de cohortes y retención se ejecutarán únicamente sobre el 40.17% de transacciones con `loyalty_card = TRUE`.

```python
# Código que generó este hallazgo
sin_customer = txn['customer_id'].isna().sum()          # 104,632
con_loyalty_false = (txn['loyalty_card'] == False).sum() # 104,632
delta = sin_customer - con_loyalty_false                  # 0
print(f'Sin customer_id: {sin_customer:,} | loyalty=FALSE: {con_loyalty_false:,} | Delta: {delta}')
# Output: Sin customer_id: 104,632 | loyalty=FALSE: 104,632 | Delta: 0
```

---

## 2. Consistencia — `total_amount` vs suma de ítems

**Pregunta:** ¿El `total_amount` en `transactions` coincide con la suma de `unit_price × quantity` en `transaction_items`?

| Métrica | Valor |
|---|---|
| Transacciones con discrepancia > $0.01 | **1,745** (1.0%) |
| Diferencia máxima | $202.68 |
| Diferencia promedio | $0.18 |

**Hallazgo:** 1,745 transacciones (1.0%) muestran una discrepancia entre el `total_amount` reportado y la suma calculada desde los ítems. La diferencia promedio es pequeña ($0.18), pero hay casos extremos de $202.68 que podrían indicar descuentos a nivel de cabecera, redondeos del sistema POS o errores de transmisión.  
**Decisión:** Para el cálculo de GMV se usará **siempre la suma desde `transaction_items` (`unit_price × quantity`)** como fuente canónica, ya que refleja el detalle real de lo vendido. El campo `total_amount` se marcará como referencial. Se escalará esta discrepancia al equipo de Ingeniería de Datos como alerta.

```python
# Código que generó este hallazgo
items_sum = items.groupby('transaction_id').apply(
    lambda x: (x['unit_price'] * x['quantity']).sum()
).reset_index()
items_sum.columns = ['transaction_id', 'gmv_calculado']

merged = txn.merge(items_sum, on='transaction_id', how='left')
merged['diff'] = abs(merged['total_amount'] - merged['gmv_calculado'])

inconsistentes = (merged['diff'] > 0.01).sum()  # 1,745
max_diff = merged['diff'].max()                  # 202.68
avg_diff = merged[merged['diff'] > 0.01]['diff'].mean()  # 0.18
print(f'Discrepancias: {inconsistentes:,} | Max: ${max_diff:.2f} | Prom: ${avg_diff:.2f}')
# Output: Discrepancias: 1,745 | Max: $202.68 | Prom: $0.18
```

---

## 3. Unicidad — Duplicados

**Pregunta:** ¿Existen `transaction_id` o `transaction_item_id` duplicados?

| Métrica | Valor |
|---|---|
| `transaction_id` duplicados | **0** |
| `transaction_item_id` duplicados | **0** |

**Hallazgo:** El dataset no presenta duplicados en las llaves primarias. ✅  
**Decisión:** Sin acción correctiva. El pipeline de carga conserva unicidad correctamente.

---

## 4. Validez — Valores fuera de rango

**Pregunta:** ¿Hay `total_amount` negativos o cero? ¿`unit_price = 0` con `was_on_promo = FALSE`?

| Métrica | Valor |
|---|---|
| `total_amount ≤ 0` | **3** (0.002%) |
| `unit_price = 0` con `was_on_promo = FALSE` | **231** |

**Hallazgo A — total_amount ≤ 0:** Solo 3 transacciones (0.002%) tienen monto cero o negativo. Pueden ser errores de ingreso o transacciones de prueba del sistema POS.  
**Decisión:** Excluir estas 3 transacciones de todos los cálculos de GMV. Marcarlas como alerta para revisión operativa.

**Hallazgo B — unit_price = 0 sin promo:** 231 ítems con precio cero sin estar marcados como en promoción. Posibles causas: artículos de cortesa, errores de digitación o categorías de bonificación.  
**Decisión:** Excluir estos ítems del cálculo de GMROI y ticket promedio. Incluir nota en el dashboard indicando que las cifras excluyen 231 líneas con precio cero.

---

## 5. Integridad Referencial

**Pregunta:** ¿Hay `store_id` en `transactions` sin registro en `stores`? ¿`vendor_id` en `products` sin registro en `vendors`?

| Verificación | Resultado |
|---|---|
| `store_id` en transactions ∉ stores | **0** |
| `vendor_id` en products ∉ vendors | **1** |
| `item_id` en transaction_items ∉ products | **0** |

**Hallazgo:** Existe **1 `vendor_id` huérfano** en `products.csv` que no tiene entrada correspondiente en `vendors.csv`. Esto significa que hay productos en el catálogo cuyo proveedor es desconocido.  
**Decisión:** Los productos con este `vendor_id` huérfano se excluirán del análisis de GMROI por proveedor. Se marcarán como `PROVEEDOR_DESCONOCIDO` en las visualizaciones de catálogo. Escalación al equipo de Compras para verificar si es un proveedor nuevo no dado de alta.

---

## 6. Frescura — Gaps de tiendas sin transacciones

**Pregunta:** ¿Hay tiendas con días consecutivos sin transacciones?

| Métrica | Valor |
|---|---|
| Tiendas con al menos 1 día sin transacciones | **1** |
| Tienda con más gaps | `TIENDA_012` (7 días) |

**Hallazgo:** `TIENDA_012` presenta 7 días sin ningún registro de venta a lo largo del período. Las demás 39 tiendas muestran actividad continua. Los 7 días podrían corresponder a cierres por inventario, festivos locales o problemas técnicos de transmisión.  
**Decisión:** Mantener la tienda en el análisis pero excluir los días con cero transacciones del cálculo de promedios diarios. Estos gaps también podrían generar falsas alarmas en la detección de quiebres de stock (Bloque 1 — Query 5); se aplicará un filtro de mínimo de historial de 7 días antes de clasificar un gap como quiebre.

---

## 7. Integridad Temporal — Transacciones antes de `opening_date`

**Pregunta:** ¿Existe alguna tienda con transacciones anteriores a su `opening_date`?

| Métrica | Valor |
|---|---|
| Transacciones antes de `opening_date` | **50** |

**Hallazgo:** 50 transacciones (0.03% del total) ocurrieron antes de la fecha oficial de apertura de su respectiva tienda. Esto puede ser por: transacciones de prueba pre-apertura, errores en la fecha de apertura registrada, o ventas de soft-opening no documentadas.  
**Decisión:** Excluir estas 50 transacciones de todos los análisis de Comp Sales y de cohortes, ya que podrían distorsionar la fecha de primera venta y el período comparable. Documentar en el README para trazabilidad.

```python
# Código que detectó transacciones pre-apertura
txn_con_apertura = txn.merge(stores[['store_id', 'opening_date']], on='store_id', how='left')
txn_con_apertura['transaction_date'] = pd.to_datetime(txn_con_apertura['transaction_date'])
txn_con_apertura['opening_date'] = pd.to_datetime(txn_con_apertura['opening_date'])

pre_apertura = txn_con_apertura[
    txn_con_apertura['transaction_date'] < txn_con_apertura['opening_date']
]
print(f'Transacciones pre-apertura: {len(pre_apertura)}')
# Output: Transacciones pre-apertura: 50
print(pre_apertura[['store_id', 'transaction_date', 'opening_date']].head())
```

---

## 8. A/B Test — Integridad de asignación CONTROL / TREATMENT

**Pregunta:** ¿Hay tiendas asignadas simultáneamente a CONTROL y TREATMENT?

| Métrica | Valor |
|---|---|
| Tiendas en ambos grupos | **2** |
| Tiendas afectadas | `TIENDA_008`, `TIENDA_037` |

**Hallazgo:** `TIENDA_008` y `TIENDA_037` aparecen en `store_promotions.csv` tanto con `variant = CONTROL` como con `variant = TREATMENT`, posiblemente en diferentes períodos o bajo diferentes `promo_name`. Esto **contamina el experimento** si las asignaciones se solapan temporalmente.  
**Decisión:** **Excluir estas dos tiendas del análisis A/B Test** (Bloque 3, Parte B). La exclusión representa el 5% de las tiendas y es la acción más conservadora para mantener la validez del experimento. Se documentará claramente en la sección de limitaciones de la presentación ejecutiva.

```python
# Código que detectó el dual-assignment
grupos = promo.groupby('store_id')['variant'].nunique()
duplicados = grupos[grupos > 1].index.tolist()  # ['TIENDA_008', 'TIENDA_037']
print(f'Tiendas en ambos grupos: {duplicados}')
# Output: Tiendas en ambos grupos: ['TIENDA_008', 'TIENDA_037']

# Verificar detalle de asignación
print(promo[promo['store_id'].isin(duplicados)][['store_id', 'variant', 'start_date', 'end_date']])
# Confirma que las asignaciones se solapan temporalmente
```

---

## Resumen Ejecutivo de Decisiones

| # | Hallazgo | Severidad | Decisión |
|---|---|---|---|
| 1 | 59.8% sin `customer_id` | Normal | Intencional — sin acción |
| 2 | 1,745 discrepancias en `total_amount` | Media | Usar suma de ítems como fuente cánonica |
| 3 | 0 duplicados | Limpio | Sin acción |
| 4A | 3 total_amount ≤ 0 | Alta | Excluir de GMV |
| 4B | 231 unit_price=0 sin promo | Media | Excluir de GMROI y ticket |
| 5 | 1 vendor_id huérfano | Media | Excluir de análisis GMROI vendor |
| 6 | TIENDA_012: 7 días sin datos | Media | Excluir días de promedios diarios |
| 7 | 50 txn antes de opening_date | Alta | Excluir de Comp Sales y cohortes |
| 8 | TIENDA_008 y TIENDA_037 en ambos grupos A/B | Crítica | Excluir del A/B Test |
