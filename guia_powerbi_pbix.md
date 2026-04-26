# Guía Power BI Desktop — Construcción del .pbix
**Prueba Técnica Diego Calderón | Retail Multiformato CAM**

> ⏱️ Tiempo estimado: 45–60 min  
> 📁 Datos en: `C:\Users\d0c00v5\Downloads\Datasets_extracted\`  
> 🎨 Colores Walmart: Azul `#0053e2` | Spark `#ffc220` | Rojo `#ea1100` | Verde `#2a8703`

---

## PASO 1 — Abrir Power BI Desktop y conectar los CSV

1. Abre **Power BI Desktop**
2. `Inicio > Obtener datos > Texto/CSV`
3. Importa los 6 archivos en este orden:

| Archivo | Nombre de tabla sugerido |
|---|---|
| `transactions.csv` | `transactions` |
| `transaction_items.csv` | `transaction_items` |
| `stores.csv` | `stores` |
| `products.csv` | `products` |
| `vendors.csv` | `vendors` |
| `store_promotions.csv` | `store_promotions` |

> Para cada uno: clic en el archivo → **Transformar datos** (no "Cargar" directo)

---

## PASO 2 — Limpieza en Power Query (Editor de consultas)

En **Power Query Editor** aplica estas transformaciones por tabla:

### transactions
```
- Filtrar: total_amount > 0  (elimina las 3 txn negativas)
- Cambiar tipo: transaction_date → Fecha
- Cambiar tipo: total_amount, discount_amount → Número decimal
- Cambiar tipo: loyalty_card → Verdadero/Falso
```

### transaction_items
```
- Cambiar tipo: unit_price, quantity → Número decimal
- Agregar columna personalizada:
  Nombre: gross_revenue
  Fórmula: = [unit_price] * [quantity]
```

### stores
```
- Cambiar tipo: opening_date → Fecha
- Cambiar tipo: size_sqm → Número entero
- Agregar columna personalizada:
  Nombre: is_comparable
  Fórmula: = if Date.From([opening_date]) <= Date.AddMonths(Date.From("2024-01-01"), -13)
              then true else false
  (Tiendas abiertas antes de Dic 2022 son comparables al inicio del período)
```

### store_promotions
```
- Filtrar: store_id ≠ "TIENDA_008" AND store_id ≠ "TIENDA_037"
  (estas 2 están en ambos grupos → contaminan el A/B)
```

Cuando termines: **Cerrar y aplicar**

---

## PASO 3 — Crear tabla de fechas (dim_date)

En **Inicio > Nueva tabla**, pega esta fórmula DAX:

```dax
dim_date =
ADDCOLUMNS(
    CALENDAR(DATE(2024,1,1), DATE(2025,6,30)),
    "Year",            YEAR([Date]),
    "Month",           MONTH([Date]),
    "MonthName",       FORMAT([Date], "MMM YYYY"),
    "Quarter",         "Q" & QUARTER([Date]) & " " & YEAR([Date]),
    "WeekNumber",      WEEKNUM([Date], 2),
    "DayOfWeek",       WEEKDAY([Date], 2),
    "IsWeekend",       IF(WEEKDAY([Date], 2) >= 6, TRUE, FALSE),
    "MonthSort",       YEAR([Date]) * 100 + MONTH([Date])
)
```

---

## PASO 4 — Crear tabla fact_sales (tabla central)

En **Inicio > Nueva tabla**:

```dax
fact_sales =
ADDCOLUMNS(
    transaction_items,
    "transaction_date",
        RELATED(transactions[transaction_date]),
    "store_id",
        RELATED(transactions[store_id]),
    "customer_id",
        RELATED(transactions[customer_id]),
    "status",
        RELATED(transactions[status]),
    "loyalty_card",
        RELATED(transactions[loyalty_card]),
    "is_returned",
        IF(RELATED(transactions[status]) = "RETURNED", TRUE, FALSE),
    "unit_cost",
        RELATED(products[cost]),
    "gross_margin",
        [unit_price] * [quantity] - RELATED(products[cost]) * [quantity]
)
```

> ⚠️ Para que RELATED funcione necesitas las relaciones del Paso 5 primero.
> Alternativa más simple: usa el merge visual de Power Query entre
> `transaction_items` → `transactions` → agrega las columnas que necesitas.

---

## PASO 5 — Modelo de datos (Star Schema)

Ve a la vista **Modelo** (ícono de diagrama en el panel izquierdo)

### Relaciones a crear

| Desde (Many) | Campo | Hacia (One) | Campo | Cardinalidad |
|---|---|---|---|---|
| `transaction_items` | `transaction_id` | `transactions` | `transaction_id` | Muchos a 1 |
| `transactions` | `store_id` | `stores` | `store_id` | Muchos a 1 |
| `transactions` | `transaction_date` | `dim_date` | `Date` | Muchos a 1 |
| `transaction_items` | `product_id` | `products` | `product_id` | Muchos a 1 |
| `products` | `vendor_id` | `vendors` | `vendor_id` | Muchos a 1 |
| `store_promotions` | `store_id` | `stores` | `store_id` | Muchos a 1 |

### Cómo crear cada relación
1. En vista Modelo, arrastra el campo de la tabla "Desde" hacia el campo de la tabla "Hacia"
2. Verifica que la cardinalidad sea **Varios a uno (*:1)**
3. Dirección del filtro: **Unidireccional** (por defecto)

---

## PASO 6 — Medidas DAX (tus 9 KPIs)

Crea una **tabla de medidas** vacía para organizarlas:
`Inicio > Especificar datos` → tabla de 1 fila/1 columna → nómbrala `_Medidas`

Luego clic derecho en `_Medidas` → **Nueva medida**:

---

### 🔵 KPI 1 — GMV Total
```dax
GMV Total =
SUMX(
    transaction_items,
    transaction_items[unit_price] * transaction_items[quantity]
)
```

---

### 🔵 KPI 2 — GMV/m² (North Star ⭐)
```dax
GMV por m2 =
DIVIDE(
    [GMV Total],
    SUMX(RELATEDTABLE(stores), stores[size_sqm]),
    0
)
```

### Variante solo tiendas comparables:
```dax
GMV m2 Comparable =
CALCULATE(
    [GMV Total],
    stores[is_comparable] = TRUE
) /
CALCULATE(
    SUM(stores[size_sqm]),
    stores[is_comparable] = TRUE
)
```

---

### 🔵 KPI 3 — Ticket Promedio
```dax
Ticket Promedio =
DIVIDE(
    CALCULATE(
        SUMX(transactions, transactions[total_amount]),
        transactions[status] = "COMPLETED"
    ),
    CALCULATE(
        COUNTROWS(transactions),
        transactions[status] = "COMPLETED"
    ),
    0
)
```

---

### 🔵 KPI 4 — Tasa de Devolución (Return Rate)
```dax
Return Rate % =
DIVIDE(
    CALCULATE(
        COUNTROWS(transactions),
        transactions[status] = "RETURNED"
    ),
    COUNTROWS(transactions),
    0
) * 100
```

---

### 🔵 KPI 5 — Penetración Tarjeta de Lealtad
```dax
Penetracion Lealtad % =
DIVIDE(
    CALCULATE(
        COUNTROWS(transactions),
        transactions[loyalty_card] = TRUE
    ),
    COUNTROWS(transactions),
    0
) * 100
```

---

### 🔵 KPI 6 — GMROI por Proveedor
```dax
GMROI =
DIVIDE(
    SUMX(
        transaction_items,
        transaction_items[unit_price] * transaction_items[quantity]
    ) -
    SUMX(
        transaction_items,
        RELATED(products[cost]) * transaction_items[quantity]
    ),
    SUMX(
        transaction_items,
        RELATED(products[cost]) * transaction_items[quantity]
    ),
    0
)
```
> ⚠️ Recuerda: GMROI < 0.35 en este dataset es una alerta de calidad de datos
> (posible que `cost` esté en unidades de caja). Documéntalo en el visual.

---

### 🔵 KPI 7 — Total Transacciones
```dax
Total Transacciones =
CALCULATE(
    COUNTROWS(transactions),
    transactions[status] <> "RETURNED"
)
```

---

### 🔵 KPI 8 — Comp Sales (necesitas 2 períodos en datos)
```dax
GMV Año Anterior =
CALCULATE(
    [GMV Total],
    DATEADD(dim_date[Date], -1, YEAR)
)

Comp Sales Growth % =
DIVIDE(
    [GMV Total] - [GMV Año Anterior],
    [GMV Año Anterior],
    0
) * 100
```

---

### 🔵 KPI 9 — GMV A/B Test por Grupo
```dax
GMV Control =
CALCULATE(
    [GMV Total],
    store_promotions[variant] = "CONTROL"
)

GMV Treatment =
CALCULATE(
    [GMV Total],
    store_promotions[variant] = "TREATMENT"
)

Lift AB % =
DIVIDE([GMV Treatment] - [GMV Control], [GMV Control], 0) * 100
```

---

## PASO 7 — Páginas del Dashboard

Crea **4 páginas** en el reporte (clic en `+` abajo):

---

### 📄 Página 1: "Resumen Ejecutivo"

**Fondo:** Rectángulo azul `#0053e2` en el header (Insert > Formas)

**Tarjetas KPI** (4 tarjetas en fila superior):
| Tarjeta | Medida | Formato |
|---|---|---|
| GMV Total | `GMV Total` | $#,0 |
| Ticket Promedio | `Ticket Promedio` | $#,0.00 |
| Return Rate | `Return Rate %` | 0.00% |
| Penetración Lealtad | `Penetracion Lealtad %` | 0.00% |

**Gráfico de área** — GMV semanal por Formato:
- Eje X: `dim_date[Date]` (jerarquía Semana)
- Eje Y: `GMV Total`
- Leyenda: `stores[format]`
- Colores: Hipermercado `#0053e2` | Super `#ffc220` | Descuento `#2a8703` | Express `#6d6d6d`

**Segmentador (Slicers)**:
- País: `stores[country]` — estilo Lista
- Formato: `stores[format]` — estilo Dropdown
- Período: `dim_date[Quarter]` — estilo Dropdown

---

### 📄 Página 2: "Productividad de Tiendas"

**Gráfico de barras horizontales** — GMV/m² por Tienda:
- Eje Y: `stores[store_name]`
- Eje X: `GMV m2 Comparable`
- Color: Barra `#0053e2`, línea de promedio `#ffc220`
- Ordenar: descendente

**Tabla de tiendas**:
| Columna | Medida/Campo |
|---|---|
| Tienda | `stores[store_name]` |
| País | `stores[country]` |
| Formato | `stores[format]` |
| GMV Total | `GMV Total` |
| GMV/m² | `GMV por m2` |
| Ticket Prom | `Ticket Promedio` |
| Return Rate | `Return Rate %` |
- Formato condicional en GMV/m²: Escala de color verde (alto) → rojo (bajo)

**Gráfico de dispersión** — GMV/m² vs Ticket Promedio:
- Eje X: `Ticket Promedio`
- Eje Y: `GMV m2 Comparable`
- Detalles: `stores[store_name]`
- Leyenda: `stores[format]`

---

### 📄 Página 3: "Análisis de Proveedores y Categorías"

**Gráfico de barras** — Pareto de Categorías (GMV):
- Eje X: `products[category]`
- Eje Y: `GMV Total`
- Ordenar: descendente
- Color: `#0053e2`
- Agregar línea de porcentaje acumulado (eje secundario)

**Tabla de Proveedores**:
| Columna | Campo/Medida |
|---|---|
| Proveedor | `vendors[vendor_name]` |
| País | `vendors[country]` |
| Tier | `vendors[tier]` |
| GMV | `GMV Total` |
| GMROI | `GMROI` |
- Formato condicional en GMROI: Rojo si < 0.5, Amarillo 0.5–1.0, Verde > 1.0
- Nota al pie: "⚠️ GMROI <0.35 puede reflejar que el campo `cost` está en unidades de caja"

**Treemap** — GMV por Categoría y Formato:
- Grupo: `products[category]`
- Detalles: `stores[format]`
- Valores: `GMV Total`

---

### 📄 Página 4: "Experimento A/B"

**Tarjetas resumen**:
| Tarjeta | Valor |
|---|---|
| GMV Control | `GMV Control` |
| GMV Treatment | `GMV Treatment` |
| Lift A/B | `Lift AB %` → mostrar -16.92% |
| p-value | Cuadro de texto estático: "0.2382 (no significativo)" |

**Gráfico de barras comparativo** — GMV Control vs Treatment por semana:
- Eje X: `dim_date[Date]` (semanas)
- Eje Y: `GMV Total`
- Leyenda: `store_promotions[variant]`
- Colores: Control `#6d6d6d` | Treatment `#0053e2`

**Cuadro de texto de interpretación** (Insert > Cuadro de texto):
```
🔬 Resultado del A/B Test
Lift: -16.92% | p-value: 0.2382
Conclusión: No hay evidencia estadística de que la
promoción TREATMENT supere al CONTROL (α=0.05).
Se recomienda NO escalar la promoción en este formato.
Nota: TIENDA_008 y TIENDA_037 excluidas por
asignación dual (contaminación del experimento).
```

---

## PASO 8 — Formato con colores Walmart

### Tema personalizado
1. `Vista > Temas > Personalizar el tema actual`
2. Colores principales:
   - Color 1: `#0053e2` (Walmart Blue)
   - Color 2: `#ffc220` (Spark Yellow)
   - Color 3: `#2a8703` (Green)
   - Color 4: `#ea1100` (Red)
   - Color 5: `#003aad` (Blue dark)
3. Fuente: Segoe UI
4. Fondo de página: `#f3f4f6` (gris claro)
5. Guardar tema como JSON para reutilizar

### Header estilo dashboard
- Insert > Formas > Rectángulo
- Relleno: gradiente `#0053e2` → `#003aad`
- Encima: cuadros de texto blancos con título y subtítulo

---

## PASO 9 — Guardar y exportar

```
Archivo > Guardar como
→ Nombre: bloque5_dashboard.pbix
→ Ubicación: C:\Users\d0c00v5\Documents\puppy_workspace\prueba_tecnica_diego_calderon\
```

---

## PASO 10 — Git commit

```bash
cd C:\Users\d0c00v5\Documents\puppy_workspace\prueba_tecnica_diego_calderon
git add bloque5_dashboard.pbix
git commit -m "feat: agregar dashboard Power BI bloque5"
git push
```

---

## ✅ Checklist final antes de la expo

- [ ] Los 6 CSVs cargados y limpios en Power Query
- [ ] Star Schema con 6 relaciones correctas
- [ ] Tabla `dim_date` creada
- [ ] 9 medidas DAX funcionando
- [ ] 4 páginas del dashboard con visuals
- [ ] Colores Walmart aplicados
- [ ] Slicers de País / Formato / Período funcionando
- [ ] Nota sobre GMROI en página de proveedores
- [ ] Nota sobre A/B Test (TIENDA_008/037 excluidas) en página 4
- [ ] Archivo guardado como .pbix y commiteado

---

## 🐶 Tips rápidos Power BI

- Si RELATED no funciona → verifica que la relación esté activa en la vista Modelo
- Para formato de moneda: clic en la medida → Herramientas de columna → Formato → Moneda
- Para línea de promedio en un gráfico de barras: Análisis > Línea de promedio → activar
- Si el modelo va lento: deshabilita la actualización automática de visuals mientras editas
- Los slicers se sincronizan entre páginas: `Vista > Sincronizar segmentadores`
