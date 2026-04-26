# Bloque 4 — Framework de KPIs: Programa de Productividad de Tiendas

**Autor:** Diego Alberto Calderón Calderón  
**Contexto:** Cadena Retail Multiformato Centroamérica | 40 tiendas | 5 países  
**Objetivo:** Framework desde cero para medir productividad, experiencia del cliente y desempeño de proveedor.  

---

## 🎯 North Star Metric

### **GMV por Metro Cuadrado Comparable (Comp GMV/m²)**

> **Fórmula:** `SUM(gross_revenue_comparable_stores) / SUM(size_sqm_comparable_stores)`  
> **Frecuencia:** Semanal  
> **Justificación:**  
>
> En retail multiformato con tiendas de tamaños muy distintos (Express vs Hipermercado), el GMV absoluto castiga tiendas pequeñas que pueden ser extraordinariamente eficientes. El **GMV/m²** normaliza por espacio y permite comparar formatos, países y períodos en la misma escala.  
> El sufijo “Comparable” excluye tiendas con menos de 13 meses de operación, garantizando que el KPI mida mejora real de productividad y no simple expansión de red.  
> Esta métrica es la que los analistas de Wall Street usan para evaluar retailers; es comprensible para el equipo directivo y directamente accionable por los gerentes de tienda (más ventas por el mismo espacio = mejor surtido, menos quiebres, mejor exhibición).

---

## 📊 KPIs del Framework

### Dimensión 1: Productividad de Tienda

---

#### KPI 1 — Comp Sales Growth (YoY)

| Campo | Detalle |
|---|---|
| **Definición** | Crecimiento de ventas en tiendas comparables respecto al mismo período del año anterior |
| **Fórmula** | `(GMV_período_actual - GMV_período_anterior) / GMV_período_anterior × 100` |
| **Frecuencia** | Mensual y acumulado YTD |
| **Fuente** | `fact_sales` JOIN `dim_store` (filtro `is_comparable = TRUE`) |
| **Target sugerido** | ≥ +5% YoY (en línea con inflación regional CA ~4-6%) |
| **¿Cómo detectas dato malo?** | Si >20% de tiendas reportan crecimiento exactamente 0% → posible falla en el pipeline de comparación de períodos. Si el KPI sube >30% en un mes sin causa conocida → verificar duplicados en carga. |

---

#### KPI 2 — GMV por Metro Cuadrado (GMV/m²) — *North Star*

| Campo | Detalle |
|---|---|
| **Definición** | Ingresos brutos generados por metro cuadrado de sala de ventas |
| **Fórmula** | `SUM(gross_revenue) / store.size_sqm` |
| **Frecuencia** | Semanal |
| **Fuente** | `fact_sales` JOIN `dim_store` |
| **Target sugerido** | P50 del formato como mínimo; tiendas en P25 entran a plan de mejora |
| **¿Cómo detectas dato malo?** | GMV/m² = 0 para una tienda activa → gap de datos. Valor 10x por encima del promedio de su formato → posible doble conteo. |

---

#### KPI 3 — Ticket Promedio por Formato

| Campo | Detalle |
|---|---|
| **Definición** | Valor promedio de una transacción completada, segmentado por formato de tienda |
| **Fórmula** | `SUM(total_amount_completadas) / COUNT(transaction_id_completadas)` |
| **Frecuencia** | Semanal |
| **Fuente** | `fact_sales` (filtro `is_returned = FALSE`) JOIN `dim_store` |
| **Target sugerido** | HIPERMERCADO ≥ $350 | SUPERMERCADO ≥ $250 | DESCUENTO ≥ $150 | EXPRESS ≥ $80 |
| **¿Cómo detectas dato malo?** | Ticket promedio < $5 o > $5,000 en cualquier semana → probable error de POS o transacción de prueba. Comparar con semana anterior; variación > ±30% sin evento documentado es alerta. |

---

### Dimensión 2: Experiencia del Cliente

---

#### KPI 4 — Tasa de Retención de Clientes Leales (M+1)

| Campo | Detalle |
|---|---|
| **Definición** | % de clientes con tarjeta de lealtad que realizan al menos 1 compra en el mes siguiente a su primera transacción |
| **Fórmula** | `COUNT(DISTINCT customer_id que compra en M+1) / COUNT(DISTINCT customer_id en cohorte M) × 100` |
| **Frecuencia** | Mensual (medición con 1 mes de rezago) |
| **Fuente** | `fact_sales` JOIN `dim_customer` (filtro `is_identified = TRUE`) |
| **Target sugerido** | ≥ 35% retención M+1 (benchmark retail Latinoamérica) |
| **¿Cómo detectas dato malo?** | Retención M+1 = 100% para cualquier cohorte → posible error en la definición de primera transacción. Retención = 0% para una cohorte grande → posible falla en el sistema de lealtad ese mes. |

---

#### KPI 5 — Tasa de Devolución (Return Rate) — *Leading Indicator*

| Campo | Detalle |
|---|---|
| **Definición** | Porcentaje de transacciones con `status = RETURNED` sobre el total. Es un indicador predictivo de insatisfacción del cliente antes de que se refleje en ventas. |
| **Fórmula** | `COUNT(status = 'RETURNED') / COUNT(*) × 100` |
| **Frecuencia** | Semanal |
| **Fuente** | `transactions` |
| **Target sugerido** | ≤ 2.5% (el dataset muestra 2.03% como base) |
| **¿Cómo detectas dato malo?** | Tasa de devolución > 10% en cualquier tienda en una semana → posible error operativo o de registro. Tasa exactamente igual durante 4 semanas consecutivas → posible que el campo dejó de actualizarse. |

> **Por qué es Leading:** Una devolución refleja una experiencia insatisfactoria ANTES de que el cliente decida no volver. Monitorear la tasa de devolución permite intervención preventiva (training de staff, mejora de calidad de producto) antes de que el KPI de retención caiga.

---

#### KPI 6 — Penetración de Tarjeta de Lealtad

| Campo | Detalle |
|---|---|
| **Definición** | % de transacciones donde el cliente usó tarjeta de lealtad (cliente identificado) |
| **Fórmula** | `COUNT(loyalty_card = TRUE) / COUNT(*) × 100` |
| **Frecuencia** | Mensual |
| **Fuente** | `transactions` |
| **Target sugerido** | ≥ 45% (base actual: 40.17%) |
| **¿Cómo detectas dato malo?** | Penetración = 0% en cualquier tienda en un día con transacciones → posible falla del sistema de lealtad en esa tienda. Salto súbito a 100% → posible bug en el campo. |

---

### Dimensión 3: Desempeño de Proveedor

---

#### KPI 7 — GMROI por Proveedor

| Campo | Detalle |
|---|---|
| **Definición** | Retorno de margen bruto por cada dólar invertido en costo de producto de ese proveedor |
| **Fórmula** | `(SUM(gross_revenue) - SUM(unit_cost × quantity)) / SUM(unit_cost × quantity)` |
| **Frecuencia** | Trimestral (revisión con proveedores) |
| **Fuente** | `fact_sales` JOIN `dim_product` JOIN `dim_vendor` |
| **Target sugerido** | GMROI ≥ 1.5 para proveedores Tier A; ≥ 1.2 para Tier B; ≥ 1.0 para Tier C |
| **¿Cómo detectas dato malo?** | GMROI < 0 (imposible si los costos están bien) → verificar que `unit_cost` no sea 0 o negativo. GMROI > 10 para un proveedor grande → posible error en el catálogo de costos. |

---

#### KPI 8 — Índice de Quiebres de Stock Estimados (Est. OOS Rate)

| Campo | Detalle |
|---|---|
| **Definición** | % de combinaciones tienda-SKU activos con al menos 1 brecha ≥3 días sin venta en el mes, sobre el total de tienda-SKUs esperados activos |
| **Fórmula** | `COUNT(store_item pairs con gap ≥3 días) / COUNT(store_item pairs activos) × 100` |
| **Frecuencia** | Mensual |
| **Fuente** | Resultado de Query 5 (Bloque 1) + `fact_sales` |
| **Target sugerido** | ≤ 5% de SKU-tienda con OOS estimado por mes |
| **¿Cómo detectas dato malo?** | OOS Rate = 100% para una tienda → posible gap de datos, no quiebre real. OOS Rate = 0% durante 2 meses consecutivos en toda la red → posible que la Query 5 no esté corriendo. |

---

#### KPI 9 — Score de Productividad de Tienda (KPI Compuesto) — *KPI Compuesto*

| Campo | Detalle |
|---|---|
| **Definición** | Índice sintético que combina GMV/m² normalizado + Tasa de Retención + Comp Sales Growth para clasificar tiendas en cuadrantes de rendimiento |
| **Fórmula** | `(Z-score de GMV/m² dentro del formato) × 0.5 + (Z-score de Retención M+1) × 0.3 + (Z-score de Comp Sales Growth) × 0.2` |
| **Frecuencia** | Mensual |
| **Fuente** | Calculado sobre KPI 2 + KPI 4 + KPI 1 |
| **Target sugerido** | Score ≥ 0 (por encima de la media del formato); Score < -1 activa plan de intervención |
| **¿Cómo detectas dato malo?** | Si alguno de los 3 componentes tiene valor nulo → el score será nulo; alertar. Si todas las tiendas tienen score exactamente 0 en un mes → error en el cálculo de Z-score (posible varianza = 0). |

> **Por qué es compuesto:** Ningún KPI aislado cuenta la historia completa. Una tienda puede tener GMV/m² alto pero retención baja (vende mucho pero a clientes que no vuelven). El score compuesto identifica tiendas genuinamente saludables y aquellas con debilidades ocultas.

---

## Resumen del Framework

| # | KPI | Dimensión | Tipo | Frecuencia | Target |
|---|---|---|---|---|---|
| 1 | Comp Sales Growth YoY | Productividad | Resultado | Mensual | ≥ +5% |
| 2 | GMV/m² ★ North Star | Productividad | Resultado | Semanal | P50 del formato |
| 3 | Ticket Promedio por Formato | Productividad | Resultado | Semanal | Por formato |
| 4 | Retención M+1 Lealtad | Cliente | Resultado | Mensual | ≥ 35% |
| 5 | Return Rate | Cliente | **Leading** | Semanal | ≤ 2.5% |
| 6 | Penetración Tarjeta Lealtad | Cliente | Resultado | Mensual | ≥ 45% |
| 7 | GMROI por Proveedor | Proveedor | Resultado | Trimestral | ≥ 1.2 |
| 8 | OOS Rate Estimado | Proveedor | Resultado | Mensual | ≤ 5% |
| 9 | Score Productividad Tienda | Multi | **Compuesto** | Mensual | ≥ 0 |
