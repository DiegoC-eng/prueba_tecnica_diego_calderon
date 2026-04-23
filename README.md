# Prueba Técnica — Data Analyst | Retail Multiformato Centroamérica

**Autor:** Diego Alberto Calderón Calderón  
**Fecha:** Abril 2025  
**Dataset:** Enero 2024 – Junio 2025 | 40 tiendas | 5 países | 4 formatos

---

## 📁 Estructura del Repositorio

```
prueba_tecnica_diego_calderon/
├── README.md                        <- Este archivo
├── bloque0_audit.py                 <- Script de auditoría de datos
├── bloque0_auditoria.md             <- Resultados de la auditoría (generado)
├── bloque1_queries.sql              <- 6 queries SQL avanzadas comentadas
├── bloque2_decisiones.md            <- Star Schema + ETL + Gobernanza
├── bloque2_modelo.pdf               <- Diagrama del Star Schema (ver nota)
├── bloque3_analisis.py              <- Análisis EDA + A/B test (Python)
├── bloque3_resultados.json          <- Resultados numéricos (generado)
├── bloque3_visualizaciones/         <- Gráficas exportadas
│   ├── p1_estacionalidad_formato.png
│   ├── p2_pareto_categorias.png
│   ├── p3_cohort_retention_heatmap.png
│   ├── p3_cohort_ticket_heatmap.png
│   ├── p4_quiebres_stock.png
│   ├── p5_hallazgo_metodo_pago.png
│   └── ab_test_results.png
├── bloque4_kpi_framework.md         <- Framework de 10 KPIs
├── bloque5_dashboard.html           <- Dashboard operativo (Chart.js + HTMX)
└── bloque5_presentacion_EN.html     <- Presentación ejecutiva en inglés (5 slides)
```

---

## ⚡ Cómo correr el código

### Pre-requisitos
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (gestor de paquetes Python)
- Los archivos CSV en `C:\Users\<tu_usuario>\Downloads\Datasets_extracted\`

> **Nota:** Si tus CSVs están en otra ruta, edita la variable `DATA_PATH` en los scripts.

### 1. Crear entorno virtual e instalar dependencias

```bash
cd prueba_tecnica_diego_calderon
uv venv --python 3.11
.venv\Scripts\activate   # Windows
# o: source .venv/bin/activate  (Mac/Linux)

uv pip install pandas matplotlib seaborn scipy numpy jinja2
```

### 2. Ejecutar Bloque 0 — Auditoría de Datos

```bash
python bloque0_audit.py
```
Genera: `bloque0_auditoria.md`

### 3. Ejecutar Bloque 3 — Análisis EDA + A/B Test

```bash
python bloque3_analisis.py
```
Genera: `bloque3_visualizaciones/` y `bloque3_resultados.json`

### 4. Ver Dashboard

Abrir en el navegador: `bloque5_dashboard.html`

### 5. Ver Presentación Ejecutiva (en inglés)

Abrir en el navegador: `bloque5_presentacion_EN.html`  
Usar el botón **"Export PDF"** para generar el PDF.

### 6. Ver Queries SQL

Abrir `bloque1_queries.sql` en cualquier editor o en BigQuery Console.  
Compatible con **BigQuery Standard SQL**.

---

## 📈 Hallazgos Clave (resumen)

| Hallazgo | Evidencia | Impacto |
|---|---|---|
| **Quiebres de stock** | 309,771 gaps ≥3 días | $339M GMV perdido estimado |
| **Categorías críticas** | Electrónica + Hogar = 80% GMV | Alta concentración de riesgo |
| **Tiendas bajo rendimiento** | 10 stores < P25 GMV/m² | -43% vs mejor en formato |
| **Retención lealtad** | 54% no vuelven en mes 1 | Oportunidad de re-engagement |
| **A/B test inválido** | p=0.241, grupos desbalanceados | NO escalar exhibición aún |
| **FORMAT sensible** | EXPRESS tiene CV=24.4% | Mayor riesgo estacional |

---

## 🤖 Uso de Inteligencia Artificial

Según las instrucciones de la prueba, se documenta el uso de IA:

### Herramienta utilizada
**Code Puppy (Fortia)** — asistente de código basado en modelos LLM (OpenAI/Gemini) integrado en el entorno de Walmart.

### Qué generó la IA
- Estructura inicial de los scripts Python (`bloque0_audit.py`, `bloque3_analisis.py`)
- Esqueleto de las queries SQL del Bloque 1
- Estructura del Star Schema en `bloque2_decisiones.md`
- HTML del dashboard y la presentación ejecutiva
- Estructura del KPI framework

### Qué modifiqué yo
- **Ajuste de lógica de negocio:** Tuve que definir los umbrales correctos (13 meses para comp sales, 3 días para quiebres, 2 centavos de tolerancia en discrepancias).
- **Interpretación de resultados:** El análisis del A/B test (grupos no balanceados, p=0.050 borderline, conclusión de no escalar) fue un juicio de negocio mío basado en los datos reales.
- **Optimización de código:** La detección de quiebres de stock original usaba loops de Python (muy lenta con 542K items). La reescribí usando operaciones vectorizadas con pandas `shift()` y `groupby`, reduciendo el tiempo de 5 minutos a 33 segundos.
- **Narrativa ejecutiva:** Las recomendaciones, los números de impacto y el razonamiento de prioridades son propios.
- **Correcciones:** Arreglé el error de encoding Unicode en Windows, corregí referencias a variables que cambiaron durante la refactorización.

### Qué validé manualmente
- Todos los resultados numéricos fueron verificados contra los datos reales (174,880 transacciones, 542,015 items)
- La fórmula de GMROI fue verificada con ejemplos manuales
- Los resultados del A/B test (p-value, IC, lift) fueron cruzados con la fórmula estándar de t-test
- La detección de tiendas con doble asignación (TIENDA_008, TIENDA_037) fue verificada directamente en el CSV

### Prompts principales utilizados
```
1. "Guíame respecto a esta prueba [instrucciones completas]"
2. "el dataset está en mi carpeta descargas una carpeta comprimida llamada Datasets"
3. [El agente exploró, leyó y analizó los datos automáticamente]
```

### Criterio en el uso de la IA
Usé la IA como un acelerador para el código repetitivo (HTML, estructuras de markdown), pero todas las decisiones analíticas y de negocio son propias. La IA no puede saber que los grupos del A/B test estaban desbalanceados hasta que los datos lo revelan — esa conclusión fue mía.

---

## 🛠️ Tecnologías utilizadas

| Herramienta | Uso |
|---|---|
| Python 3.11 | Análisis de datos (Bloques 0, 3) |
| pandas, numpy | Manipulación y análisis de datos |
| matplotlib, seaborn | Visualizaciones |
| scipy.stats | T-test del A/B test |
| BigQuery SQL | Queries analíticas (Bloque 1) |
| HTML + Chart.js + HTMX + Tailwind | Dashboard + Presentación |
| uv | Gestión de entorno Python |
| Git | Control de versiones |

---

*Prueba Técnica — Data Analyst — Cadena de Retail Multiformato — Centroamérica*
