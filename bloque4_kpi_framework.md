# Bloque 4 — Framework de KPIs desde Cero

**Autor:** Diego A. Calderón C.  
**Programa:** Mejora de Productividad de Tiendas | Cadena Retail Multiformato CAM

---

## 🎯 North Star Metric

**GMV por Metro Cuadrado (Semanal)**  
`GMV_sqm = GMV_semanal_tienda / size_sqm`

**Justificación:**  
Este KPI captura en una sola cifra la productividad real de cada tienda independientemente de su tamaño o formato. Un HIPERMERCADO de 7,000 m² y un SUPERMERCADO de 1,700 m² son directamente comparables. Es la métrica que mejor correlaciona con rentabilidad operativa y es la base de todos los demás KPIs del programa. Además es el KPI que el VP de Operaciones puede ver en 5 segundos y saber si una tienda va bien o mal.

---

## Tabla de KPIs

### KPI 1: GMV por Metro Cuadrado (North Star)

| Campo | Detalle |
|---|---|
| **Definición** | Ventas brutas totales generadas por cada metro cuadrado de sala de ventas |
| **Fórmula** | `SUM(total_amount) / size_sqm` donde `status='COMPLETED'` y `total_amount > 0` |
| **Frecuencia** | Semanal (lunes a domingo), con acumulado mensual |
| **Fuente de datos** | `fact_transactions` JOIN `dim_store` |
| **Target sugerido** | P75 del formato en el mismo país. Tiendas < P25 = BAJO_RENDIMIENTO |
| **¿Cómo detectas dato malo?** | Si GMV/m² cae > 40% respecto a la semana anterior sin cierre de tienda. Si es $0 = tienda sin enviar datos. Si sube > 200% = posible doble conteo. |

---

### KPI 2: Comp Sales Growth % (YoY)

| Campo | Detalle |
|---|---|
| **Definición** | Crecimiento de ventas comparables año sobre año, solo tiendas con ≥13 meses de operación |
| **Fórmula** | `(GMV_periodo_actual - GMV_mismo_periodo_anterior) / GMV_mismo_periodo_anterior * 100` |
| **Frecuencia** | Mensual y YTD (Year To Date) |
| **Fuente de datos** | `fact_transactions` JOIN `dim_store` (filtro `is_comparable = TRUE`) |
| **Target sugerido** | +3% mensual mínimo; +8% para tiendas en mercados de alto crecimiento (GT, SV) |
| **¿Cómo detectas dato malo?** | Comp Sales > +50% o < -50% sin causa conocida (reapertura, remodelación) = alerta. Verificar que el periodo anterior tenga datos completos. |

---

### KPI 3: Ticket Promedio por Formato

| Campo | Detalle |
|---|---|
| **Definición** | Valor promedio de cada transacción completada, segmentado por formato de tienda |
| **Fórmula** | `AVG(total_amount)` donde `status='COMPLETED'` y `total_amount > 0` |
| **Frecuencia** | Semanal |
| **Fuente de datos** | `fact_transactions` JOIN `dim_store` |
| **Target sugerido** | HIPERMERCADO: >$85 | SUPERMERCADO: >$45 | DESCUENTO: >$25 | EXPRESS: >$15 |
| **¿Cómo detectas dato malo?** | Ticket promedio < $5 (posible falla en carga, solo items de precio bajo). Ticket > $5,000 en formatos pequeños (transacción atípica o error). |

---

### KPI 4: Tasa de Retención de Clientes Leales (Mes 3)

| Campo | Detalle |
|---|---|
| **Definición** | Porcentaje de clientes con tarjeta de lealtad que vuelven a comprar en el 3er mes después de su primera compra |
| **Fórmula** | `Clientes_cohorte_que_compraron_en_mes_3 / Tamaño_cohorte * 100` |
| **Frecuencia** | Mensual (se calcula 3 meses en retrospectiva) |
| **Fuente de datos** | `fact_transactions` + `dim_customer` |
| **Target sugerido** | ≥30% de retención en mes 3 (benchmark retail CAM) |
| **¿Cómo detectas dato malo?** | Retención mes 3 > 100% = error de cálculo (customer_id duplicado). Retención = 0% para cohorte grande = falla en captura de loyalty_card. |

---

### KPI 5: GMROI por Proveedor (Leading Indicator 📊)

| Campo | Detalle |
|---|---|
| **Definición** | Retorno sobre la inversión en inventario por proveedor. KPI predictivo: un GMROI < 1 hoy predice problemas de rentabilidad futuros |
| **Fórmula** | `(GMV - Costo_Total) / Costo_Total` por vendor+categoría en últimos 90 días |
| **Frecuencia** | Mensual |
| **Fuente de datos** | `fact_transaction_items` JOIN `dim_product` JOIN `dim_vendor` |
| **Target sugerido** | GMROI ≥ 1.5 (margen bruto ≥60% sobre costo). Vendedores con GMROI < 1 = revisión de contrato |
| **¿Cómo detectas dato malo?** | GMROI = 0 o negativo con GMV alto = `unit_cost` nulo o cero en `products`. GMROI > 10 = posible error en costo unitario. |

---

### KPI 6: Tasa de Quiebres de Stock Activos

| Campo | Detalle |
|---|---|
| **Definición** | Porcentaje de SKUs activos (vendidos en últimos 30 días) que llevan 3+ días sin ventas en al menos una tienda |
| **Fórmula** | `SKUs_con_gap_activo_≥3_dias / Total_SKUs_activos * 100` |
| **Frecuencia** | Diaria (es un leading indicator de ventas perdidas) |
| **Fuente de datos** | `fact_transaction_items` (ventana rodante de 30 días) |
| **Target sugerido** | < 5% de SKUs activos con quiebre. Categorias de alimentos: < 3% |
| **¿Cómo detectas dato malo?** | Tasa de quiebres = 100% = la tienda no envió datos ese día (no hay ventas de nada). Tasa = 0% durante semanas seguidas = posible falla en detección. |

---

### KPI 7: Índice de Productividad de Tienda — IPS (KPI Compuesto ⭐)

| Campo | Detalle |
|---|---|
| **Definición** | KPI compuesto que combina GMV/m², retención de clientes y Comp Sales para dar una puntuación única de salud de tienda |
| **Fórmula** | `IPS = (GMV_sqm_score * 0.5) + (Comp_Sales_score * 0.3) + (Retention_score * 0.2)` donde cada score = percentil de la tienda en su formato (0-100) |
| **Frecuencia** | Mensual |
| **Fuente de datos** | Calculado a partir de KPI 1, KPI 2 y KPI 4 |
| **Target sugerido** | IPS ≥ 60 = saludable | 40-60 = atención | < 40 = intervención gerencial |
| **¿Cómo detectas dato malo?** | IPS de una tienda cambia > 30 puntos en un mes sin evento conocido = revisar los 3 componentes individualmente. |

---

### KPI 8: Frecuencia de Compra de Clientes Leales

| Campo | Detalle |
|---|---|
| **Definición** | Número promedio de visitas mensuales de clientes con tarjeta de lealtad |
| **Fórmula** | `COUNT(transaction_id) / COUNT(DISTINCT customer_id)` donde `loyalty_card=TRUE` y `status='COMPLETED'`, agrupado por mes |
| **Frecuencia** | Mensual |
| **Fuente de datos** | `fact_transactions` |
| **Target sugerido** | ≥2.5 visitas/mes para HIPERMERCADO | ≥4 visitas/mes para EXPRESS |
| **¿Cómo detectas dato malo?** | Frecuencia > 30 visitas/mes por cliente = posible ID compartido o error de registro de loyalty. Frecuencia baja repentina = falla en captura de tarjeta en caja. |

---

### KPI 9: GMV de Promociones / GMV Total (Promo Mix)

| Campo | Detalle |
|---|---|
| **Definición** | Porcentaje del GMV que fue generado por items en promoción. Mide dependencia del negocio en descuentos |
| **Fórmula** | `SUM(line_gmv WHERE was_on_promo=TRUE) / SUM(line_gmv_total) * 100` |
| **Frecuencia** | Semanal |
| **Fuente de datos** | `fact_transaction_items` |
| **Target sugerido** | 20-35% del GMV en promo = rango saludable. > 50% = riesgo de erosión de margen |
| **¿Cómo detectas dato malo?** | Promo Mix = 100% = todos los items marcados como promo (error en flag). Promo Mix = 0% durante una semana de campaña activa = falla en registro de promos. |

---

### KPI 10: Velocidad de Venta por SKU (Sell-Through Rate Leading)

| Campo | Detalle |
|---|---|
| **Definición** | Unidades vendidas por día por SKU en cada tienda. KPI predictivo: cae antes de un quiebre de stock |
| **Fórmula** | `SUM(quantity) / COUNT(DISTINCT sale_date)` por item_id + store_id en ventana de 14 días |
| **Frecuencia** | Diaria (rolling 14 días) |
| **Fuente de datos** | `fact_transaction_items` |
| **Target sugerido** | Varía por categoría. Se usa baseline histórico: alerta si cae > 50% vs promedio 8 semanas |
| **¿Cómo detectas dato malo?** | Velocidad = 0 para item activo = quiebre o sin datos. Pico extremo (10x promedio) = posible promoción no registrada o error de carga de cantidad. |

---

## Resumen del Framework

| # | KPI | Dimensión | Tipo | Frecuencia |
|---|---|---|---|---|
| 1 | GMV/m² (North Star) | Productividad Tienda | Resultado | Semanal |
| 2 | Comp Sales % YoY | Productividad Tienda | Resultado | Mensual |
| 3 | Ticket Promedio | Productividad Tienda | Resultado | Semanal |
| 4 | Retención Mes 3 | Experiencia Cliente | Resultado | Mensual |
| 5 | GMROI por Vendor | Desempeño Proveedor | **Leading** | Mensual |
| 6 | Tasa Quiebres Stock | Productividad Tienda | **Leading** | Diaria |
| 7 | Índice Productividad (IPS) | Productividad Tienda | **Compuesto** | Mensual |
| 8 | Frecuencia de Compra | Experiencia Cliente | Resultado | Mensual |
| 9 | Promo Mix % | Desempeño Proveedor | Resultado | Semanal |
| 10 | Velocidad de Venta | Desempeño Proveedor | **Leading** | Diaria |

**Leading indicators:** KPI 5, 6, 10 (predicen problemas antes de que impacten el P&L)  
**KPI Compuesto:** KPI 7 (IPS, calculado a partir de KPI 1, 2 y 4)
