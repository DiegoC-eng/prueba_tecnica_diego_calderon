"""
Generador de Power BI Project (.pbip) para Prueba Técnica Diego Calderón.

Genera la estructura de carpetas PBIP con:
  - Modelo completo (6 tablas CSV + dim_date + 9 medidas DAX)
  - Relaciones Star Schema
  - Reporte con 4 páginas pre-nombradas

Diego solo necesita:
  1. Abrir la carpeta .pbip en Power BI Desktop
  2. Actualizar la ruta del datasource si difiere
  3. Refrescar datos
  4. Añadir los visuals en cada página
"""

import json
import os
import uuid
import shutil
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
DATA_DIR = r"C:\Users\d0c00v5\Downloads\Datasets_extracted"
OUT_DIR  = Path(r"C:\Users\d0c00v5\Documents\puppy_workspace\prueba_tecnica_diego_calderon\bloque5_dashboard.pbip")
PROJECT_NAME = "bloque5_dashboard"

# ── HELPERS ─────────────────────────────────────────────────────────────────

def new_id():
    return str(uuid.uuid4())

def m_csv_source(filename, col_types):
    """Genera la expresión M para leer un CSV desde DATA_DIR."""
    filepath = DATA_DIR.replace("\\", "\\\\") + "\\\\" + filename
    type_lines = ",\n".join(
        f'                    {{\"Name\", type {t}}}' for _, t in col_types
    )
    col_rename = ",\n".join(
        f'                    {{\"Column{i+1}\", \"{name}\"}}' for i, (name, _) in enumerate(col_types)
    )

    # Simple M expression — let PBI autodetect headers
    path = DATA_DIR.replace("\\", "\\\\") + "\\\\" + filename
    lines = [
        "let",
        f'    Source = Csv.Document(',
        f'        File.Contents(\"{DATA_DIR}\\\\{filename}\"),',
        f'        [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.None]',
        f'    ),',
        f'    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])',
        "in",
        "    Headers"
    ]
    return "\n".join(lines)


# ── TABLAS ──────────────────────────────────────────────────────────────────

def make_table_csv(name, filename, columns):
    """Crea una tabla importada desde CSV."""
    m_expr = [
        "let",
        f'    Source = Csv.Document(',
        f'        File.Contents("{DATA_DIR}\\\\{filename}"),',
         '        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]',
         '    ),',
         '    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])',
        "in",
        "    Headers"
    ]
    return {
        "name": name,
        "columns": columns,
        "partitions": [{
            "name": name,
            "dataView": "full",
            "source": {
                "type": "m",
                "expression": m_expr
            }
        }]
    }


def col(name, data_type, is_hidden=False, format_string=None):
    c = {
        "name": name,
        "dataType": data_type,
        "lineageTag": new_id(),
        "summarizeBy": "none"
    }
    if is_hidden:
        c["isHidden"] = True
    if format_string:
        c["formatString"] = format_string
    return c


def measure(name, expression, format_string=None, description=""):
    m = {
        "name": name,
        "expression": expression,
        "lineageTag": new_id()
    }
    if format_string:
        m["formatString"] = format_string
    if description:
        m["description"] = description
    return m


# ── DEFINICIÓN DEL MODELO ───────────────────────────────────────────────────

def build_model():
    # ---- transactions ----
    t_transactions = make_table_csv("transactions", "transactions.csv", [
        col("transaction_id",   "string"),
        col("store_id",         "string"),
        col("customer_id",      "string"),
        col("transaction_date", "dateTime"),
        col("total_amount",     "double",  format_string="\\$#,0.00"),
        col("discount_amount",  "double",  format_string="\\$#,0.00"),
        col("payment_method",   "string"),
        col("status",           "string"),
        col("loyalty_card",     "boolean"),
    ])

    # ---- transaction_items ----
    t_items = make_table_csv("transaction_items", "transaction_items.csv", [
        col("transaction_item_id", "string"),
        col("transaction_id",      "string"),
        col("product_id",          "string"),
        col("quantity",            "int64"),
        col("unit_price",          "double", format_string="\\$#,0.00"),
    ])

    # ---- stores ----
    t_stores = make_table_csv("stores", "stores.csv", [
        col("store_id",     "string"),
        col("store_name",   "string"),
        col("country",      "string"),
        col("city",         "string"),
        col("format",       "string"),
        col("region",       "string"),
        col("size_sqm",     "int64"),
        col("opening_date", "dateTime"),
    ])

    # ---- products ----
    t_products = make_table_csv("products", "products.csv", [
        col("product_id",  "string"),
        col("item_name",   "string"),
        col("brand",       "string"),
        col("category",    "string"),
        col("department",  "string"),
        col("vendor_id",   "string"),
        col("cost",        "double", format_string="\\$#,0.00"),
    ])

    # ---- vendors ----
    t_vendors = make_table_csv("vendors", "vendors.csv", [
        col("vendor_id",        "string"),
        col("vendor_name",      "string"),
        col("country",          "string"),
        col("tier",             "string"),
        col("is_shared_catalog","boolean"),
    ])

    # ---- store_promotions ----
    t_promos = make_table_csv("store_promotions", "store_promotions.csv", [
        col("store_id",   "string"),
        col("promo_name", "string"),
        col("variant",    "string"),
        col("start_date", "dateTime"),
        col("end_date",   "dateTime"),
    ])

    # ---- dim_date (tabla calculada DAX) ----
    dim_date_expr = [
        "ADDCOLUMNS(",
        "    CALENDAR(DATE(2024,1,1), DATE(2025,6,30)),",
        '    "Year",       YEAR([Date]),',
        '    "Month",      MONTH([Date]),',
        '    "MonthName",  FORMAT([Date], \"MMM YYYY\"),',
        '    "Quarter",    \"Q\" & QUARTER([Date]) & \" \" & YEAR([Date]),',
        '    "WeekNumber", WEEKNUM([Date], 2),',
        '    "DayOfWeek",  WEEKDAY([Date], 2),',
        '    "IsWeekend",  IF(WEEKDAY([Date],2)>=6, TRUE, FALSE),',
        '    "MonthSort",  YEAR([Date])*100 + MONTH([Date])',
        ")"
    ]
    t_dim_date = {
        "name": "dim_date",
        "columns": [
            col("Date",        "dateTime"),
            col("Year",        "int64"),
            col("Month",       "int64"),
            col("MonthName",   "string"),
            col("Quarter",     "string"),
            col("WeekNumber",  "int64"),
            col("DayOfWeek",   "int64"),
            col("IsWeekend",   "boolean"),
            col("MonthSort",   "int64",  is_hidden=True),
        ],
        "partitions": [{
            "name": "dim_date",
            "dataView": "full",
            "source": {
                "type": "calculated",
                "expression": dim_date_expr
            }
        }]
    }

    # ---- Tabla de medidas ----
    t_medidas = {
        "name": "_Medidas",
        "columns": [col("Placeholder", "string", is_hidden=True)],
        "partitions": [{
            "name": "_Medidas",
            "dataView": "full",
            "source": {
                "type": "m",
                "expression": [
                    "let Source = #table({\"Placeholder\"}, {}) in Source"
                ]
            }
        }],
        "measures": [
            measure(
                "GMV Total",
                [
                    "SUMX(",
                    "    transaction_items,",
                    "    transaction_items[unit_price] * transaction_items[quantity]",
                    ")"
                ],
                format_string="\\$#,0",
                description="Gross Merchandise Value: SUM(unit_price x quantity). Fuente canónica (no total_amount)."
            ),
            measure(
                "GMV Comparable",
                [
                    "CALCULATE(",
                    "    [GMV Total],",
                    "    FILTER(stores, stores[opening_date] < DATE(2024,1,1))",
                    ")"
                ],
                format_string="\\$#,0",
                description="GMV solo tiendas con apertura anterior a Ene 2024 (13+ meses)."
            ),
            measure(
                "GMV por m2",
                [
                    "VAR gmv = [GMV Total]",
                    "VAR sqm = SUMX(RELATEDTABLE(stores), stores[size_sqm])",
                    "RETURN DIVIDE(gmv, sqm, 0)"
                ],
                format_string="\\$#,0.00",
                description="North Star: GMV / metros cuadrados de sala de ventas."
            ),
            measure(
                "Ticket Promedio",
                [
                    "DIVIDE(",
                    "    CALCULATE(SUM(transactions[total_amount]), transactions[status] = \"COMPLETED\"),",
                    "    CALCULATE(COUNTROWS(transactions),           transactions[status] = \"COMPLETED\"),",
                    "    0",
                    ")"
                ],
                format_string="\\$#,0.00",
                description="Valor promedio de transacciones completadas."
            ),
            measure(
                "Return Rate %",
                [
                    "DIVIDE(",
                    "    CALCULATE(COUNTROWS(transactions), transactions[status] = \"RETURNED\"),",
                    "    COUNTROWS(transactions),",
                    "    0",
                    ") * 100"
                ],
                format_string="0.00\"%\"",
                description="Tasa de devolución. Leading indicator de insatisfacción. Target: \u22642.5%"
            ),
            measure(
                "Penetracion Lealtad %",
                [
                    "DIVIDE(",
                    "    CALCULATE(COUNTROWS(transactions), transactions[loyalty_card] = TRUE),",
                    "    COUNTROWS(transactions),",
                    "    0",
                    ") * 100"
                ],
                format_string="0.00\"%\"",
                description="% de txn con tarjeta de lealtad. Target actual: 40.17% \u2192 objetivo: 45%."
            ),
            measure(
                "GMROI",
                [
                    "VAR revenue = SUMX(transaction_items, transaction_items[unit_price] * transaction_items[quantity])",
                    "VAR cost    = SUMX(transaction_items, RELATED(products[cost])         * transaction_items[quantity])",
                    "RETURN DIVIDE(revenue - cost, cost, 0)"
                ],
                format_string="0.00",
                description="Gross Margin Return on Inventory. \u26a0\ufe0f Valores <0.35 pueden indicar que products.cost est\u00e1 en unidades de caja."
            ),
            measure(
                "Total Transacciones",
                [
                    "CALCULATE(COUNTROWS(transactions), transactions[status] <> \"RETURNED\")"
                ],
                format_string="#,0",
                description="Transacciones completadas y pendientes (excluye devueltas)."
            ),
            measure(
                "GMV Ano Anterior",
                [
                    "CALCULATE([GMV Total], DATEADD(dim_date[Date], -1, YEAR))"
                ],
                format_string="\\$#,0",
                description="GMV del mismo per\u00edodo, 1 a\u00f1o antes."
            ),
            measure(
                "Comp Sales Growth %",
                [
                    "DIVIDE([GMV Total] - [GMV Ano Anterior], [GMV Ano Anterior], 0) * 100"
                ],
                format_string="0.00\"%\"",
                description="Crecimiento YoY en tiendas comparables. Target: \u22655%."
            ),
            measure(
                "GMV Control",
                [
                    "CALCULATE([GMV Total], store_promotions[variant] = \"CONTROL\")"
                ],
                format_string="\\$#,0",
                description="GMV del grupo CONTROL del A/B test (excluye TIENDA_008 y TIENDA_037)."
            ),
            measure(
                "GMV Treatment",
                [
                    "CALCULATE([GMV Total], store_promotions[variant] = \"TREATMENT\")"
                ],
                format_string="\\$#,0",
                description="GMV del grupo TREATMENT del A/B test."
            ),
            measure(
                "Lift AB %",
                [
                    "DIVIDE([GMV Treatment] - [GMV Control], [GMV Control], 0) * 100"
                ],
                format_string="0.00\"%\"",
                description="Lift del experimento A/B. Resultado real: -16.92% (p=0.2382, no significativo)."
            ),
        ]
    }

    # ── RELACIONES ──────────────────────────────────────────────────────────
    relationships = [
        {
            "name": new_id(),
            "fromTable": "transaction_items",
            "fromColumn": "transaction_id",
            "toTable": "transactions",
            "toColumn": "transaction_id"
        },
        {
            "name": new_id(),
            "fromTable": "transactions",
            "fromColumn": "store_id",
            "toTable": "stores",
            "toColumn": "store_id"
        },
        {
            "name": new_id(),
            "fromTable": "transactions",
            "fromColumn": "transaction_date",
            "toTable": "dim_date",
            "toColumn": "Date"
        },
        {
            "name": new_id(),
            "fromTable": "transaction_items",
            "fromColumn": "product_id",
            "toTable": "products",
            "toColumn": "product_id"
        },
        {
            "name": new_id(),
            "fromTable": "products",
            "fromColumn": "vendor_id",
            "toTable": "vendors",
            "toColumn": "vendor_id"
        },
        {
            "name": new_id(),
            "fromTable": "store_promotions",
            "fromColumn": "store_id",
            "toTable": "stores",
            "toColumn": "store_id"
        },
    ]

    # ── BIM completo ────────────────────────────────────────────────────────
    bim = {
        "name": "Model",
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": [
                t_transactions,
                t_items,
                t_stores,
                t_products,
                t_vendors,
                t_promos,
                t_dim_date,
                t_medidas,
            ],
            "relationships": relationships,
            "annotations": [
                {"name": "PBIDesktopVersion", "value": "2.138"},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "1"}
            ]
        }
    }
    return bim


# ── REPORTE (4 páginas básicas) ─────────────────────────────────────────────

def build_report_layout():
    """Layout mínimo con 4 páginas nombradas. Diego añade los visuals."""
    def page(name, display_name, order):
        return {
            "id": new_id(),
            "name": name,
            "displayName": display_name,
            "filters": "[]",
            "ordinal": order,
            "visualContainers": [],
            "width": 1280,
            "height": 720,
            "defaultFilterActionType": 1
        }

    return {
        "id": new_id(),
        "theme": {
            "name": "Walmart CAM",
            "version": "1.0",
            "dataColors": [
                "#0053e2", "#ffc220", "#2a8703",
                "#ea1100", "#003aad", "#6d6d6d"
            ]
        },
        "sections": [
            page("ResumenEjecutivo",       "1 | Resumen Ejecutivo",        0),
            page("ProductividadTiendas",   "2 | Productividad de Tiendas", 1),
            page("ProveedoresCategorias",  "3 | Proveedores y Categorías", 2),
            page("ABTest",                "4 | Experimento A/B",          3),
        ],
        "config": json.dumps({
            "version": "5.47",
            "themeCollection": {
                "baseTheme": {"name": "CY24SU05", "version": "5.47"}
            }
        }),
        "filters": "[]",
        "pods": []
    }


# ── ESCRITURA DE ARCHIVOS ────────────────────────────────────────────────────

def write_pbip():
    import sys
    # Limpiar si ya existe
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    dataset_dir = OUT_DIR / f"{PROJECT_NAME}.Dataset"
    report_dir  = OUT_DIR / f"{PROJECT_NAME}.Report"
    dataset_dir.mkdir()
    report_dir.mkdir()

    # 1. Archivo .pbip principal
    pbip_content = {
        "version": "1.0",
        "artifacts": [
            {
                "report": {
                    "path": f"{PROJECT_NAME}.Report"
                }
            }
        ],
        "settings": {
            "enableTmdlSave": False
        }
    }
    (OUT_DIR / f"{PROJECT_NAME}.pbip").write_text(
        json.dumps(pbip_content, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 2. model.bim (modelo de datos)
    bim = build_model()
    (dataset_dir / "model.bim").write_text(
        json.dumps(bim, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 3. .platform para Dataset
    platform_dataset = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {
            "type": "SemanticModel",
            "displayName": PROJECT_NAME
        },
        "config": {
            "version": "2.0",
            "logicalId": new_id()
        }
    }
    (dataset_dir / ".platform").write_text(
        json.dumps(platform_dataset, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 4. definition.pbidataset
    pbidataset = {
        "version": "1.0",
        "settings": {}
    }
    (dataset_dir / "definition.pbidataset").write_text(
        json.dumps(pbidataset, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 5. Report/Layout
    layout = build_report_layout()
    (report_dir / "report.json").write_text(
        json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 6. .platform para Report
    platform_report = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {
            "type": "Report",
            "displayName": PROJECT_NAME
        },
        "config": {
            "version": "2.0",
            "logicalId": new_id()
        }
    }
    (report_dir / ".platform").write_text(
        json.dumps(platform_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 7. definition.pbireport
    pbireport = {
        "version": "1.0",
        "datasetReference": {
            "byPath": {"path": f"../{PROJECT_NAME}.Dataset"},
            "byConnection": None
        }
    }
    (report_dir / "definition.pbireport").write_text(
        json.dumps(pbireport, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        f"",
        f"PBIP generado en: {OUT_DIR}",
        f"",
        "Estructura:",
    ]
    for f in sorted(OUT_DIR.rglob("*")):
        if f.is_file():
            rel = f.relative_to(OUT_DIR.parent)
            lines.append(f"  {rel}")
    lines += [
        "",
        "Proximos pasos:",
        "  1. Abre Power BI Desktop",
        "  2. Archivo > Abrir informe > Examinar > selecciona:",
        f"     {OUT_DIR / PROJECT_NAME}.pbip",
        "  3. Si pide credenciales del CSV: elegir Anonimo",
        "  4. Inicio > Actualizar",
        "  5. Modelo listo! Agrega los visuals en las 4 paginas",
    ]
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    write_pbip()
