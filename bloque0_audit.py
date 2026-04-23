"""
Bloque 0 — Auditoría de Calidad de Datos
=========================================
Este script audita el dataset completo y genera bloque0_auditoria.md
con todos los hallazgos documentados y las decisiones tomadas.

Autor: Diego A. Calderón C.
IA utilizada: Code Puppy (basado en OpenAI/Gemini). Prompts y validaciones
              documentados en README.md.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# ── Configuración de rutas ──────────────────────────────────────────────────
DATA_PATH = Path(r"C:\Users\d0c00v5\Downloads\Datasets_extracted")
OUT_MD    = Path("bloque0_auditoria.md")

# ── Carga de datos ──────────────────────────────────────────────────────────
print("[INFO] Cargando datasets...")
stores       = pd.read_csv(DATA_PATH / "stores.csv")
products     = pd.read_csv(DATA_PATH / "products.csv")
vendors      = pd.read_csv(DATA_PATH / "vendors.csv")
promotions   = pd.read_csv(DATA_PATH / "store_promotions.csv")
transactions = pd.read_csv(
    DATA_PATH / "transactions.csv",
    parse_dates=["transaction_date"]
)
tx_items = pd.read_csv(DATA_PATH / "transaction_items.csv")
print(f"[INFO] Transacciones: {len(transactions):,} | Items: {len(tx_items):,}")

# ── Helper para formatear hallazgos ────────────────────────────────────────
findings = []

def finding(dimension, pregunta, evidencia, decision):
    """Agrega un hallazgo al reporte."""
    findings.append({
        "dimension": dimension,
        "pregunta":  pregunta,
        "evidencia": evidencia,
        "decision":  decision,
    })

# ═══════════════════════════════════════════════════════════════════════════
# 1. COMPLETITUD
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 1. Completitud...")

# 1a. customer_id nulo
total_tx       = len(transactions)
null_customer  = transactions["customer_id"].isna().sum()
pct_null_cust  = null_customer / total_tx * 100
finding(
    "Completitud",
    "¿Qué porcentaje de transacciones no tiene customer_id?",
    f"{null_customer:,} de {total_tx:,} transacciones ({pct_null_cust:.1f}%) no tienen customer_id. "
    f"Las restantes {total_tx - null_customer:,} ({100-pct_null_cust:.1f}%) tienen customer_id.",
    "ACEPTAR — El ~60% sin customer_id corresponde a compradores sin tarjeta de lealtad. "
    "Se tratarán como clientes anónimos. Para análisis de cohortes se usará solo loyalty_card=TRUE."
)

# 1b. loyalty_card FALSE vs TRUE
loyalty_false = (transactions["loyalty_card"] == False).sum()
loyalty_true  = (transactions["loyalty_card"] == True).sum()
pct_false     = loyalty_false / total_tx * 100
finding(
    "Completitud",
    "¿Qué porcentaje de transacciones tiene loyalty_card = FALSE?",
    f"{loyalty_false:,} transacciones ({pct_false:.1f}%) tienen loyalty_card=FALSE. "
    f"{loyalty_true:,} ({100-pct_false:.1f}%) tienen loyalty_card=TRUE. "
    f"Consistencia con customer_id nulo: {abs(null_customer - loyalty_false):,} diferencia.",
    "ACEPTAR — loyalty_card=FALSE son compradores sin programa de lealtad. "
    "La diferencia con customer_id nulo indica que algunos clientes con tarjeta no se identificaron en caja."
)

# ═══════════════════════════════════════════════════════════════════════════
# 2. CONSISTENCIA — total_amount vs sum(unit_price * quantity)
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 2. Consistencia total_amount...")

# Calcular suma de items por transacción
item_totals = (
    tx_items
    .assign(line_total=lambda df: df["unit_price"] * df["quantity"])
    .groupby("transaction_id")["line_total"]
    .sum()
    .reset_index()
    .rename(columns={"line_total": "items_total"})
)

# Merge con transactions
consistency = transactions[["transaction_id", "total_amount"]].merge(
    item_totals, on="transaction_id", how="inner"
)
consistency["diff"] = (consistency["total_amount"] - consistency["items_total"]).abs()
consistency["discrepant"] = consistency["diff"] > 0.02  # tolerancia de 2 centavos

n_discrepant  = consistency["discrepant"].sum()
pct_discrepant = n_discrepant / len(consistency) * 100
max_diff       = consistency["diff"].max()
median_diff    = consistency.loc[consistency["discrepant"], "diff"].median() if n_discrepant > 0 else 0

finding(
    "Consistencia",
    "¿El total_amount coincide con la suma de unit_price × quantity en transaction_items?",
    f"Se compararon {len(consistency):,} transacciones con sus items. "
    f"{n_discrepant:,} ({pct_discrepant:.1f}%) tienen discrepancia > $0.02. "
    f"Diferencia máxima: ${max_diff:.2f}. Mediana de discrepancias: ${median_diff:.2f}.",
    "ALERTA — Si la discrepancia es < 1% se acepta (redondeos/descuentos de nivel transacción). "
    "Para análisis de GMV se usará total_amount como fuente de verdad. "
    "Se excluirán transacciones con discrepancia > $10 si las hay."
)

# ═══════════════════════════════════════════════════════════════════════════
# 3. UNICIDAD — transaction_id duplicados
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 3. Unicidad...")

dup_tx = transactions["transaction_id"].duplicated().sum()
dup_items = tx_items["transaction_item_id"].duplicated().sum()

finding(
    "Unicidad",
    "¿Existen transaction_id duplicados?",
    f"transactions.csv: {dup_tx:,} transaction_id duplicados de {total_tx:,} total. "
    f"transaction_items.csv: {dup_items:,} transaction_item_id duplicados de {len(tx_items):,} total.",
    "IGNORAR si = 0. Si hay duplicados, se deduplica por transaction_id manteniendo el último registro."
)

# ═══════════════════════════════════════════════════════════════════════════
# 4. VALIDEZ
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 4. Validez...")

# 4a. total_amount <= 0
neg_zero_amount = (transactions["total_amount"] <= 0).sum()
finding(
    "Validez",
    "¿Hay total_amount negativos o cero?",
    f"{neg_zero_amount:,} transacciones tienen total_amount ≤ 0 "
    f"({neg_zero_amount/total_tx*100:.2f}% del total).",
    "EXCLUIR — Total negativo indica reverso/devolución o error de carga. "
    "Se excluirán del análisis de GMV pero se documentarán por separado."
)

# 4b. unit_price = 0 con was_on_promo = False
zero_price_nopromo = tx_items[
    (tx_items["unit_price"] == 0) & (tx_items["was_on_promo"] == False)
].shape[0]
zero_price_promo   = tx_items[
    (tx_items["unit_price"] == 0) & (tx_items["was_on_promo"] == True)
].shape[0]
total_zero_price   = (tx_items["unit_price"] == 0).sum()

finding(
    "Validez",
    "¿Hay unit_price = 0 con was_on_promo = FALSE?",
    f"{total_zero_price:,} items tienen unit_price=0 en total. "
    f"De estos, {zero_price_nopromo:,} tienen was_on_promo=FALSE (sospechoso) "
    f"y {zero_price_promo:,} tienen was_on_promo=TRUE (posible item regalo/promo).",
    "MARCAR COMO ALERTA — unit_price=0 con was_on_promo=FALSE es anómalo. "
    "Se excluyen del cálculo de GMV y GMROI. Se notifica al equipo de datos."
)

# ═══════════════════════════════════════════════════════════════════════════
# 5. INTEGRIDAD REFERENCIAL
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 5. Integridad referencial...")

# 5a. store_id en transactions no en stores
valid_stores   = set(stores["store_id"])
tx_stores      = set(transactions["store_id"])
orphan_stores  = tx_stores - valid_stores
n_orphan_tx    = transactions[transactions["store_id"].isin(orphan_stores)].shape[0]

finding(
    "Integridad Referencial",
    "¿Hay store_id en transactions que no existan en stores?",
    f"{len(orphan_stores)} store_id huérfanos encontrados: {orphan_stores if orphan_stores else 'Ninguno'}. "
    f"Afecta {n_orphan_tx:,} transacciones.",
    "EXCLUIR transacciones con store_id sin registro en stores. "
    "Si es 0, sin acción requerida."
)

# 5b. vendor_id en products no en vendors
valid_vendors    = set(vendors["vendor_id"])
product_vendors  = set(products["vendor_id"])
orphan_vendors   = product_vendors - valid_vendors
n_orphan_prods   = products[products["vendor_id"].isin(orphan_vendors)].shape[0]

finding(
    "Integridad Referencial",
    "¿Hay vendor_id en products que no existan en vendors?",
    f"{len(orphan_vendors)} vendor_id huérfanos: {orphan_vendors if orphan_vendors else 'Ninguno'}. "
    f"Afecta {n_orphan_prods:,} productos.",
    "EXCLUIR productos sin proveedor registrado para análisis de GMROI. "
    "Se documenta como alerta de gobernanza."
)

# ═══════════════════════════════════════════════════════════════════════════
# 6. FRESCURA — gaps de días sin transacciones por tienda
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 6. Frescura / gaps...")

# Fechas únicas por tienda
dates_by_store = (
    transactions
    .groupby("store_id")["transaction_date"]
    .apply(lambda x: sorted(x.dt.date.unique()))
)

gap_records = []
for store, dates in dates_by_store.items():
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i-1]).days
        if gap > 1:  # más de 1 día de diferencia
            gap_records.append({
                "store_id": store,
                "gap_start": dates[i-1],
                "gap_end":   dates[i],
                "gap_days":  gap - 1
            })

gap_df = pd.DataFrame(gap_records)
if len(gap_df) > 0:
    stores_with_gaps = gap_df["store_id"].nunique()
    max_gap          = gap_df["gap_days"].max()
    large_gaps       = gap_df[gap_df["gap_days"] > 6]  # gaps > 1 semana
    gap_summary = (
        f"{len(gap_df):,} gaps detectados en {stores_with_gaps} tiendas. "
        f"Gap máximo: {max_gap} días. "
        f"Gaps > 1 semana: {len(large_gaps)} (potencialmente sospechosos)."
    )
else:
    gap_summary = "No se detectaron gaps de días consecutivos sin transacciones."

finding(
    "Frescura",
    "¿Hay tiendas con gaps de días consecutivos sin transacciones? ¿Son esperables o sospechosos?",
    gap_summary,
    "INVESTIGAR gaps > 7 días — podrían ser cierres temporales (inventario, festivos) "
    "o fallas en el envío de datos. Los gaps de 1-2 días en domingos/festivos son esperables. "
    "Gaps > 14 días se marcan como ALERTA y se excluyen del cálculo de Comp Sales."
)

# ═══════════════════════════════════════════════════════════════════════════
# 7. INTEGRIDAD TEMPORAL — transacciones antes de opening_date
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 7. Integridad temporal...")

stores["opening_date"] = pd.to_datetime(stores["opening_date"])
tx_with_store = transactions.merge(
    stores[["store_id", "opening_date"]], on="store_id", how="inner"
)
early_tx = tx_with_store[
    tx_with_store["transaction_date"] < tx_with_store["opening_date"]
]

finding(
    "Integridad Temporal",
    "¿Existe alguna tienda con transacciones anteriores a su opening_date?",
    f"{len(early_tx):,} transacciones tienen fecha anterior a la opening_date de su tienda. "
    f"Tiendas afectadas: {early_tx['store_id'].nunique() if len(early_tx) > 0 else 0}.",
    "EXCLUIR — Transacciones previas a apertura son errores de carga. "
    "Se eliminan del análisis."
)

# ═══════════════════════════════════════════════════════════════════════════
# 8. A/B TEST — tiendas en CONTROL y TREATMENT simultáneamente
# ═══════════════════════════════════════════════════════════════════════════
print("[AUDIT] 8. Integridad del A/B test...")

# Tiendas por promo y variante
promo_variants = (
    promotions
    .groupby(["store_id", "promo_name"])["variant"]
    .apply(set)
    .reset_index()
)
promo_variants["both_groups"] = promo_variants["variant"].apply(
    lambda v: "CONTROL" in v and "TREATMENT" in v
)
dual_assignment = promo_variants[promo_variants["both_groups"]]

finding(
    "A/B Test",
    "¿Hay tiendas asignadas simultáneamente a CONTROL y TREATMENT en store_promotions?",
    f"{len(dual_assignment):,} tienda(s) están asignadas a ambos grupos en la misma promoción: "
    f"{dual_assignment[['store_id','promo_name']].to_string() if len(dual_assignment) > 0 else 'Ninguna'}.",
    "EXCLUIR tiendas con doble asignación del análisis A/B. "
    "Contaminan los resultados del test al pertenecer a ambos grupos."
)

# ═══════════════════════════════════════════════════════════════════════════
# GENERAR MARKDOWN
# ═══════════════════════════════════════════════════════════════════════════
print("[INFO] Generando bloque0_auditoria.md...")

md_lines = [
    "# Bloque 0 — Auditoría de Calidad de Datos",
    "",
    f"**Fecha de auditoría:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    f"**Dataset:** Enero 2024 – Junio 2025 | 40 tiendas | 5 países | 4 formatos",
    "",
    "## Resumen del Dataset",
    "",
    f"| Tabla | Registros | Columnas |",
    f"|---|---|---|",
    f"| stores | {len(stores):,} | {len(stores.columns)} |",
    f"| products | {len(products):,} | {len(products.columns)} |",
    f"| vendors | {len(vendors):,} | {len(vendors.columns)} |",
    f"| store_promotions | {len(promotions):,} | {len(promotions.columns)} |",
    f"| transactions | {len(transactions):,} | {len(transactions.columns)} |",
    f"| transaction_items | {len(tx_items):,} | {len(tx_items.columns)} |",
    "",
    "---",
    "",
    "## Hallazgos por Dimensión",
    "",
]

for f in findings:
    md_lines += [
        f"### 🔍 {f['dimension']}: {f['pregunta']}",
        "",
        f"**Evidencia:** {f['evidencia']}",
        "",
        f"**Decisión:** {f['decision']}",
        "",
        "---",
        "",
    ]

# Resumen ejecutivo de decisiones
md_lines += [
    "## Resumen de Decisiones para Bloques Siguientes",
    "",
    "| Hallazgo | Acción |",
    "|---|---|",
    "| ~60% sin customer_id | Aceptar, usar loyalty_card=TRUE para cohortes |",
    "| Discrepancias total_amount vs items | Usar total_amount como fuente de verdad |",
    "| Duplicados de transaction_id | Deduplicar si existen |",
    "| total_amount ≤ 0 | Excluir del análisis de GMV |",
    "| unit_price=0 sin promo | Excluir de GMROI, marcar alerta |",
    "| Store_id huérfanos | Excluir transacciones sin tienda |",
    "| Vendor_id huérfanos | Excluir de análisis GMROI |",
    "| Gaps > 14 días | Excluir de Comp Sales, investigar |",
    "| Transacciones pre-apertura | Excluir |",
    "| Tiendas en ambos grupos A/B | Excluir del experimento |",
    "",
    "---",
    "",
    "*Auditoría generada automáticamente por `bloque0_audit.py`*",
]

OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
print(f"[OK] {OUT_MD} generado exitosamente.")
print("\n=== RESUMEN DE HALLAZGOS ===")
for f in findings:
    print(f"  [{f['dimension']}] {f['evidencia'][:120].encode('ascii','replace').decode()}...")
