# prueba_tecnica_diego_calderon

**Data Analyst Technical Test — Retail Chain Multiformato Centroamérica**  
Autor: Diego Alberto Calderón Calderón  
Fecha: Abril 2026  

---

## Estructura del Repositorio

```
prueba_tecnica_diego_calderon/
├── README.md                      # Este archivo
├── bloque0_auditoria.md           # Auditoría de calidad de datos
├── bloque1_queries.sql            # 6 queries SQL comentadas
├── bloque2_modelo.pdf             # Diagrama Star Schema
├── bloque2_modelo_diagram.png     # Diagrama Star Schema (PNG)
├── bloque2_decisiones.md          # Decisiones de diseño + ETL + gobernanza
├── bloque3_analisis.md            # Narrativa del análisis exploratorio + A/B
├── bloque3_analisis.py            # Script Python que genera todas las visualizaciones
├── bloque3_visualizaciones/       # Imágenes exportadas
│   ├── p1_estacionalidad_formato.png
│   ├── p2_pareto_categorias.png
│   ├── p3_cohortes_lealtad.png
│   ├── p4_quiebres_stock.png
│   ├── p5_metodos_pago_pais.png
│   ├── ab_test_resultado.png
│   └── star_schema_diagram.png
├── bloque4_kpi_framework.md       # Framework de KPIs
├── bloque5_dashboard.pbix         # Dashboard Power BI (*)
├── bloque5_presentacion_EN.pdf    # Presentación ejecutiva en inglés (*)
├── explore_data.py                # Script de exploración inicial
└── generate_star_schema.py        # Generador del diagrama Star Schema
```

`(*)` Archivos que requieren herramientas externas (Power BI Desktop, editor PDF).

---

## Cómo Reproducir el Análisis

### Prerrequisitos
- Python 3.11+ con `uv` instalado
- Los 6 archivos CSV del dataset en `C:\Users\<usuario>\Downloads\Datasets_extracted\`  
  (o modificar la variable `DATA_DIR` en los scripts)

### Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd prueba_tecnica_diego_calderon

# 2. Crear entorno virtual
uv venv .venv

# 3. Instalar dependencias
uv pip install pandas numpy matplotlib seaborn scipy statsmodels
```

### Ejecutar el análisis

```bash
# Auditoría de datos (stats para bloque0)
.venv/Scripts/python.exe explore_data.py

# Análisis exploratorio + A/B test + visualizaciones
.venv/Scripts/python.exe bloque3_analisis.py
# Output: bloque3_visualizaciones/*.png + ab_test_results.txt

# Generar diagrama Star Schema
.venv/Scripts/python.exe generate_star_schema.py
# Output: bloque2_modelo_diagram.png, bloque3_visualizaciones/star_schema_diagram.png
```

### SQL Queries (Bloque 1)

Las queries en `bloque1_queries.sql` están escritas en **BigQuery Standard SQL**.

**Para ejecutarlas en BigQuery:**

1. Abre [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Crea un dataset: `retail_cam` en tu proyecto GCP
3. Carga cada CSV como tabla (Schema: Autodetectar):

```
Consola BigQuery > tu-proyecto > retail_cam > Crear tabla
  Origen: Subir archivo CSV
  Tablas: transactions, transaction_items, stores, products, vendors, store_promotions
```

4. Reemplaza el prefijo de tabla en cada query:

```sql
-- Cambia esto:
FROM transactions
-- Por esto:
FROM `tu-proyecto.retail_cam.transactions`
```

5. Ejecuta cada query directamente en el editor SQL de BigQuery.

---

## Dataset

| Archivo | Filas | Descripción |
|---|---|---|
| `transactions.csv` | 174,880 | Transacciones maestro |
| `transaction_items.csv` | 542,015 | Líneas de detalle |
| `stores.csv` | 40 | Tiendas (8 por país × 5 países) |
| `products.csv` | 200 | Catálogo de productos |
| `vendors.csv` | 30 | Proveedores |
| `store_promotions.csv` | 42 | Asignaciones A/B |

Período: **Enero 2024 – Junio 2025** (18 meses)  
GMV total: **$48.7M** | Países: CR, GT, HN, SV, NI  
Formatos: HIPERMERCADO, SUPERMERCADO, DESCUENTO, EXPRESS  

---

## Decisiones de Calidad (post-auditoría)

- Se excluyen 3 transacciones con `total_amount ≤ 0`
- Se excluyen 50 transacciones anteriores a `opening_date` de la tienda
- Para GMV se usa `SUM(unit_price × quantity)` como fuente cánonica (no `total_amount`)
- Del A/B test se excluyen `TIENDA_008` y `TIENDA_037` (asignadas a ambos grupos)
- Ver detalle completo en `bloque0_auditoria.md`

---

## Documentación de Uso de IA

Se utilizó **Fortia (Code Puppy)** como asistente de IA durante esta prueba.

### Qué generó la IA
- Estructura base de los scripts Python (explore_data.py, bloque3_analisis.py)
- Borradores iniciales de los archivos `.md`
- Scaffolding del diagrama Star Schema en matplotlib
- Sugerencias de estructura para las queries SQL
### Qué modifiqué y validé manualmente

- **A/B Test:** Verifiqué manualmente que el merge de grupos (CONTROL/TREATMENT) estaba correcto revisando `store_promotions.csv` directamente. Corrí el t-test dos veces cambiando el orden del merge para confirmar que el signo del lift era correcto (-16.92%, no +16.92%). El resultado negativo me sorprendió y fue lo primero que quise descartar como error.
- **Auditoría de consistencia:** Verifiqué manualmente que la tasa de 59.83% sin `customer_id` coincide exactamente con `loyalty_card = FALSE`. La diferencia es 0 filas — ese cruce no es obvio y requiere revisar dos columnas independientes.
- **GMV canónico:** La decisión de usar `SUM(unit_price × quantity)` en vez de `total_amount` fue mía después de detectar 1,745 discrepancias en la auditoría. No era el resultado esperado cuando empecé a explorar el dataset.
- **GMROI sospechoso:** Detecté que todos los GMROI calculados son <0.35 (atípico para retail). Mi hipótesis es que `cost` en `products.csv` puede estar en unidades de caja y no unitario. Documenté esto como alerta en bloque2 y bloque3 en vez de asumir que el número es correcto.
- **Contexto regional:** El contexto de bancarización por país (CR >68%, NI ~30%), aguinaldo de diciembre en CA, y la frase sobre Bitcoin en SV son conocimiento propio que la IA no tenía en el prompt.
- **Cohortes pequeñas:** La decisión de excluir las cohortes Jul-Ago 2024 (n<3) del reporte interpretativo por ser estadísticamente no confiables fue mía, aunque el código las mantiene para transparencia.
- **Queries SQL:** Todas las queries fueron revisadas lógicamente. La Query 5 (islands & gaps) cambió de un enfoque inicial de self-join que era demasiado lento a window functions con LAG() — esa decisión fue mía tras probar ambos enfoques.
- **Todos los números en los markdowns** se verificaron contra el output real de los scripts Python y DuckDB.

### Prompts principales usados
- *"Genera un script Python para auditar la calidad de datos en 6 CSVs de retail con las dimensiones: completitud, consistencia, unicidad, validez, integridad referencial, frescura, integridad temporal y validez del A/B test"*
- *"Genera visualizaciones para análisis exploratorio de retail: estacionalidad semanal, pareto por categoría, heatmap de cohortes, proxy de quiebres de stock, y boxplot para A/B test usando colores Walmart"*
- *"Ayuda a estructurar un star schema en BigQuery para KPIs de retail multiformato considerando que el 60% de las transacciones no tiene customer_id"*

### Criterio de uso
La IA se usó como acelerador para el código repetitivo y el formato, nunca como reemplazo del criterio analítico. Todas las conclusiones, decisiones de negocio y recomendaciones son propias.

---

## Resultados Clave

| Bloque | Hallazgo Principal |
|---|---|
| Auditoría | TIENDA_008 y TIENDA_037 contaminadas en A/B; 50 txn pre-apertura excluidas |
| SQL | GMROI por vendor permite identificar proveedores que destruyen margen |
| Modelo | Star Schema granular a nivel ítem; flag `is_comparable` pre-computado |
| Análisis | A/B Test no significativo (p=0.24); mayor caída de retención en M+1→M+2 |
| KPIs | North Star: GMV/m² comparable; Return Rate como leading indicator |