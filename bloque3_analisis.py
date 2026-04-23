"""
Bloque 3 — Análisis Exploratorio + Experimentación A/B
=======================================================
Este script genera todos los gráficos exportados + el análisis del A/B test.
Salidas: bloque3_visualizaciones/ + bloque3_analisis.html

Autor: Diego A. Calderón C.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # no requiere pantalla (headless)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from scipy import stats
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# ── Configuración general ──────────────────────────────────────────────────
DATA_PATH = Path(r"C:\Users\d0c00v5\Downloads\Datasets_extracted")
VIZ_PATH  = Path("bloque3_visualizaciones")
VIZ_PATH.mkdir(exist_ok=True)

# Paleta de colores Walmart
WALMART_BLUE    = "#0053e2"
WALMART_SPARK   = "#ffc220"
WALMART_RED     = "#ea1100"
WALMART_GREEN   = "#2a8703"
WALMART_GRAY    = "#6d6d6d"
PALETTE = [WALMART_BLUE, WALMART_SPARK, WALMART_RED, WALMART_GREEN, "#00a8e0", "#7b3f9e"]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "#f8f9fa",
    "font.family":      "sans-serif",
    "axes.spines.top":  False,
    "axes.spines.right": False,
})

print("[INFO] Cargando datasets...")
stores       = pd.read_csv(DATA_PATH / "stores.csv", parse_dates=["opening_date"])
products     = pd.read_csv(DATA_PATH / "products.csv")
promotions   = pd.read_csv(DATA_PATH / "store_promotions.csv",
                           parse_dates=["start_date", "end_date"])
transactions = pd.read_csv(DATA_PATH / "transactions.csv",
                           parse_dates=["transaction_date"])
tx_items     = pd.read_csv(DATA_PATH / "transaction_items.csv")

print(f"[INFO] TX: {len(transactions):,} | Items: {len(tx_items):,}")

# ── Limpieza básica (decisiones del Bloque 0) ────────────────────────────────
# Excluir reversos y canceladas
tx_clean = transactions[
    (transactions["total_amount"] > 0) &
    (transactions["status"] == "COMPLETED") &
    (transactions["store_id"].isin(stores["store_id"]))
].copy()

# Agregar información de tienda
tx_clean = tx_clean.merge(stores[["store_id","country","format","size_sqm","region"]],
                          on="store_id", how="left")

# Columnas temporales útiles
tx_clean["year"]         = tx_clean["transaction_date"].dt.year
tx_clean["month"]        = tx_clean["transaction_date"].dt.month
tx_clean["week"]         = tx_clean["transaction_date"].dt.isocalendar().week.astype(int)
tx_clean["year_week"]   = tx_clean["transaction_date"].dt.to_period("W").dt.start_time
tx_clean["year_month"]  = tx_clean["transaction_date"].dt.to_period("M").dt.start_time

print(f"[INFO] TX limpias: {len(tx_clean):,}")


# ================================================================
# PREGUNTA 1: Estacionalidad por formato (GMV semanal)
# ================================================================
print("[P1] Estacionalidad por formato...")

gmv_weekly_fmt = (
    tx_clean
    .groupby(["year_week", "format"])["total_amount"]
    .sum()
    .reset_index()
    .rename(columns={"total_amount": "gmv"})
)

fig, ax = plt.subplots(figsize=(14, 6))
formats = gmv_weekly_fmt["format"].unique()
for i, fmt in enumerate(sorted(formats)):
    data = gmv_weekly_fmt[gmv_weekly_fmt["format"] == fmt]
    ax.plot(data["year_week"], data["gmv"] / 1e6,
            label=fmt, color=PALETTE[i], linewidth=2)

ax.set_title("GMV Semanal por Formato de Tienda\nEne 2024 – Jun 2025",
             fontsize=14, fontweight="bold", pad=15)
ax.set_xlabel("Semana", fontsize=11)
ax.set_ylabel("GMV (millones $)", fontsize=11)
ax.legend(title="Formato", fontsize=9)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.1f}M"))
plt.xticks(rotation=45, fontsize=8)
plt.tight_layout()
fig.savefig(VIZ_PATH / "p1_estacionalidad_formato.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("[OK] p1_estacionalidad_formato.png")

# Coeficiente de variación por formato (mayor CV = más sensible a estacionalidad)
format_cv = (
    gmv_weekly_fmt
    .groupby("format")["gmv"]
    .agg(["mean", "std"])
    .assign(cv=lambda df: df["std"] / df["mean"] * 100)
    .sort_values("cv", ascending=False)
)
print("[P1] Coeficiente de variación (estacionalidad):\n", format_cv)


# ================================================================
# PREGUNTA 2: Pareto de categorías por formato
# ================================================================
print("[P2] Pareto de categorías...")

# Join items con productos y transacciones
items_full = (
    tx_items
    .merge(products[["item_id", "category"]], on="item_id", how="left")
    .merge(tx_clean[["transaction_id", "format", "country"]], on="transaction_id", how="inner")
)
items_full["line_gmv"] = items_full["unit_price"] * items_full["quantity"]

# GMV por categoría y formato
cat_fmt_gmv = (
    items_full
    .groupby(["format", "category"])["line_gmv"]
    .sum()
    .reset_index()
)

# Plot Pareto por formato
formats_list = sorted(cat_fmt_gmv["format"].unique())
fig, axes = plt.subplots(1, len(formats_list), figsize=(5 * len(formats_list), 7))
if len(formats_list) == 1:
    axes = [axes]

for ax, fmt in zip(axes, formats_list):
    data = (cat_fmt_gmv[cat_fmt_gmv["format"] == fmt]
            .sort_values("line_gmv", ascending=False)
            .reset_index(drop=True))
    data["pct"] = data["line_gmv"] / data["line_gmv"].sum() * 100
    data["cum_pct"] = data["pct"].cumsum()

    colors = [WALMART_BLUE if cp <= 80 else WALMART_GRAY for cp in data["cum_pct"]]
    ax.bar(data["category"], data["pct"], color=colors)
    ax2 = ax.twinx()
    ax2.plot(data["category"], data["cum_pct"], color=WALMART_RED,
             marker="o", markersize=4, linewidth=2)
    ax2.axhline(80, color=WALMART_RED, linestyle="--", alpha=0.5, linewidth=1)
    ax2.set_ylim(0, 110)
    ax2.set_ylabel("% Acumulado", fontsize=9)

    ax.set_title(f"{fmt}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Categoría", fontsize=9)
    ax.set_ylabel("% del GMV", fontsize=9)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)

fig.suptitle("Pareto de Categorías por Formato de Tienda",
             fontsize=14, fontweight="bold", y=1.02)
plt.tight_layout()
fig.savefig(VIZ_PATH / "p2_pareto_categorias.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("[OK] p2_pareto_categorias.png")


# ================================================================
# PREGUNTA 3: Cohortes de lealtad
# ================================================================
print("[P3] Cohortes de lealtad...")

# Solo clientes identificados con loyalty
loyalty_tx = tx_clean[
    (tx_clean["loyalty_card"] == True) &
    (tx_clean["customer_id"].notna())
].copy()

# Cohorte = mes de primera compra
first_purchase = (
    loyalty_tx
    .groupby("customer_id")["transaction_date"]
    .min()
    .dt.to_period("M")
    .rename("cohort")
    .reset_index()
)

loyalty_tx = loyalty_tx.merge(first_purchase, on="customer_id", how="left")
loyalty_tx["tx_period"] = loyalty_tx["transaction_date"].dt.to_period("M")
loyalty_tx["months_since"] = (
    loyalty_tx["tx_period"].dt.to_timestamp() -
    loyalty_tx["cohort"].dt.to_timestamp()
).dt.days // 30

# Tamaño de cohorte
cohort_sizes = first_purchase.groupby("cohort")["customer_id"].count()

# Retención por cohorte y mes
retention = (
    loyalty_tx
    .groupby(["cohort", "months_since"])["customer_id"]
    .nunique()
    .reset_index()
)
retention = retention.merge(
    cohort_sizes.rename("cohort_size"), on="cohort"
)
retention["retention_pct"] = retention["customer_id"] / retention["cohort_size"] * 100

# Pivot para heatmap
retention_pivot = retention[
    retention["months_since"].between(0, 6)
].pivot_table(
    index="cohort", columns="months_since", values="retention_pct"
).round(1)

fig, ax = plt.subplots(figsize=(12, 8))
sns.heatmap(
    retention_pivot,
    annot=True, fmt=".0f",
    cmap="Blues",
    linewidths=0.5,
    ax=ax,
    cbar_kws={"label": "% Retención"},
    vmin=0, vmax=100
)
ax.set_title("Cohortes de Retención — Clientes con Tarjeta de Lealtad\n(% que compra en cada mes post-adquisición)",
             fontsize=13, fontweight="bold", pad=15)
ax.set_xlabel("Meses desde primera compra", fontsize=11)
ax.set_ylabel("Cohorte (mes de primera compra)", fontsize=11)
plt.tight_layout()
fig.savefig(VIZ_PATH / "p3_cohort_retention_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("[OK] p3_cohort_retention_heatmap.png")

# Ticket promedio por cohorte y mes
ticket_cohort = (
    loyalty_tx[loyalty_tx["months_since"].between(0, 6)]
    .groupby(["cohort", "months_since"])["total_amount"]
    .mean()
    .reset_index()
)
ticket_pivot = ticket_cohort.pivot_table(
    index="cohort", columns="months_since", values="total_amount"
).round(2)

fig, ax = plt.subplots(figsize=(12, 8))
sns.heatmap(
    ticket_pivot,
    annot=True, fmt=".0f",
    cmap="YlOrRd",
    linewidths=0.5,
    ax=ax,
    cbar_kws={"label": "Ticket Promedio ($)"}
)
ax.set_title("Ticket Promedio por Cohorte y Mes\nClientes con Tarjeta de Lealtad",
             fontsize=13, fontweight="bold", pad=15)
ax.set_xlabel("Meses desde primera compra", fontsize=11)
ax.set_ylabel("Cohorte", fontsize=11)
plt.tight_layout()
fig.savefig(VIZ_PATH / "p3_cohort_ticket_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("[OK] p3_cohort_ticket_heatmap.png")


# ================================================================
# PREGUNTA 4: Quiebres de stock y su impacto (vectorizado)
# ================================================================
print("[P4] Quiebres de stock (vectorizado)...")

# Join items con transacciones limpias (solo columnas necesarias)
items_tx = tx_items[["transaction_id", "item_id", "unit_price", "quantity"]].merge(
    tx_clean[["transaction_id", "store_id", "transaction_date"]],
    on="transaction_id", how="inner"
)
items_tx["sale_date"] = items_tx["transaction_date"].dt.normalize()
items_tx["line_gmv"]  = items_tx["unit_price"] * items_tx["quantity"]

# Ventas diarias por tienda-item
daily_sales = (
    items_tx
    .groupby(["store_id", "item_id", "sale_date"])["line_gmv"]
    .sum()
    .reset_index()
)

# Solo combos con >= 10 dias de historial
history_count = daily_sales.groupby(["store_id", "item_id"])["sale_date"].count()
active_combos = history_count[history_count >= 10].index
daily_sales = daily_sales.set_index(["store_id", "item_id"])
daily_sales = daily_sales[daily_sales.index.isin(active_combos)].reset_index()

# Calcular GMV promedio diario por combo
avg_daily = (
    daily_sales.groupby(["store_id", "item_id"])["line_gmv"]
    .mean()
    .rename("avg_daily_gmv")
    .reset_index()
)

# Calcular gap usando LAG vectorizado con shift
daily_sorted = daily_sales.sort_values(["store_id", "item_id", "sale_date"])
daily_sorted["prev_date"] = daily_sorted.groupby(["store_id", "item_id"])["sale_date"].shift(1)
daily_sorted["gap_days"]  = (
    (daily_sorted["sale_date"] - daily_sorted["prev_date"]).dt.days - 1
)

# Filtrar gaps >= 3 dias
gaps_df = daily_sorted[daily_sorted["gap_days"] >= 3].copy()
gaps_df = gaps_df.rename(columns={"prev_date": "gap_start", "sale_date": "gap_end"})
gaps_df = gaps_df.merge(avg_daily, on=["store_id", "item_id"], how="left")
gaps_df["lost_gmv"] = gaps_df["avg_daily_gmv"] * gaps_df["gap_days"]
gaps_df = gaps_df.merge(products[["item_id", "category"]], on="item_id", how="left")

if len(gaps_df) > 0:
    lost_by_cat = (
        gaps_df
        .groupby("category")["lost_gmv"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(lost_by_cat["category"], lost_by_cat["lost_gmv"] / 1e3, color=WALMART_RED)
    ax.set_xlabel("GMV Estimado Perdido (miles $)", fontsize=11)
    ax.set_title("GMV Estimado Perdido por Quiebres de Stock\npor Categoría",
                 fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}K"))
    plt.tight_layout()
    fig.savefig(VIZ_PATH / "p4_quiebres_stock.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] p4_quiebres_stock.png | {len(gaps_df):,} gaps | "
          f"GMV perdido: ${gaps_df['lost_gmv'].sum():,.0f}")
else:
    print("[P4] No se detectaron quiebres significativos.")


# ================================================================
# PREGUNTA 5: Hallazgo libre — Impacto del método de pago en ticket
# ================================================================
print("[P5] Hallazgo libre: Método de pago vs ticket...")

payment_analysis = (
    tx_clean
    .groupby(["payment_method", "format"])
    .agg(
        avg_ticket=("total_amount", "mean"),
        num_tx=("transaction_id", "count"),
        pct_loyalty=("loyalty_card", "mean")
    )
    .reset_index()
)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Ticket promedio por método de pago
payment_avg = tx_clean.groupby("payment_method")["total_amount"].mean().sort_values(ascending=False)
axes[0].bar(payment_avg.index, payment_avg.values,
            color=[WALMART_BLUE, WALMART_SPARK, WALMART_RED][:len(payment_avg)])
axes[0].set_title("Ticket Promedio por Método de Pago", fontsize=12, fontweight="bold")
axes[0].set_ylabel("Ticket Promedio ($)", fontsize=10)
axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}"))
for bar in axes[0].patches:
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f"${bar.get_height():.1f}", ha="center", va="bottom", fontsize=10)

# Distribución de métodos de pago por país
payment_country = (
    tx_clean
    .groupby(["country", "payment_method"])["transaction_id"]
    .count()
    .unstack(fill_value=0)
)
payment_country_pct = payment_country.div(payment_country.sum(axis=1), axis=0) * 100
payment_country_pct.plot(kind="bar", ax=axes[1], color=PALETTE[:len(payment_country_pct.columns)])
axes[1].set_title("Mix de Métodos de Pago por País", fontsize=12, fontweight="bold")
axes[1].set_ylabel("% de Transacciones", fontsize=10)
axes[1].set_xlabel("País", fontsize=10)
axes[1].legend(title="Método", fontsize=8)
plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=0)

fig.suptitle("Hallazgo Libre: Comportamiento por Método de Pago",
             fontsize=13, fontweight="bold")
plt.tight_layout()
fig.savefig(VIZ_PATH / "p5_hallazgo_metodo_pago.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("[OK] p5_hallazgo_metodo_pago.png")


# ================================================================
# PARTE B: ANÁLISIS A/B TEST — Exhibición en Punto de Venta
# ================================================================
print("[AB] Analizando A/B test...")

# El test corrió Sep-Oct 2024 (6 semanas)
TEST_START = pd.Timestamp("2024-09-01")
TEST_END   = pd.Timestamp("2024-10-12")
PRE_START  = pd.Timestamp("2024-07-01")  # 8 semanas pre-test para comparabilidad
PRE_END    = pd.Timestamp("2024-08-31")

# 1. Obtener grupos del experimento
test_stores = promotions[promotions["promo_name"] == "Exhibicion_Q3_2024"][["store_id","variant"]].drop_duplicates()

# Detectar tiendas en ambos grupos (contaminadas)
dual = test_stores.groupby("store_id")["variant"].apply(set)
contaminated = dual[dual.apply(len) > 1].index.tolist()
print(f"[AB] Tiendas en ambos grupos (excluir): {contaminated}")
test_stores_clean = test_stores[~test_stores["store_id"].isin(contaminated)]

control_stores   = test_stores_clean[test_stores_clean["variant"] == "CONTROL"]["store_id"].tolist()
treatment_stores = test_stores_clean[test_stores_clean["variant"] == "TREATMENT"]["store_id"].tolist()
print(f"[AB] CONTROL: {len(control_stores)} tiendas | TREATMENT: {len(treatment_stores)} tiendas")

# 2. Validación: comparabilidad pre-test (GMV base)
pre_tx = tx_clean[
    (tx_clean["transaction_date"].between(PRE_START, PRE_END)) &
    (tx_clean["store_id"].isin(control_stores + treatment_stores))
]

pre_gmv = (
    pre_tx
    .groupby("store_id")["total_amount"]
    .sum()
    .reset_index()
    .merge(test_stores_clean, on="store_id")
)

print("\n[AB] GMV pre-test por grupo:")
print(pre_gmv.groupby("variant")["total_amount"].describe())

# T-test de comparabilidad pre-test
c_pre = pre_gmv[pre_gmv["variant"]=="CONTROL"]["total_amount"]
t_pre = pre_gmv[pre_gmv["variant"]=="TREATMENT"]["total_amount"]
stat_pre, pval_pre = stats.ttest_ind(c_pre, t_pre)
print(f"[AB] Comparabilidad pre-test: t={stat_pre:.3f}, p={pval_pre:.3f}")
comparable = "SÍ" if pval_pre > 0.05 else "NO (grupos no comparables)"
print(f"[AB] ¿Grupos comparables? {comparable}")

# 3. GMV durante el test
test_tx = tx_clean[
    (tx_clean["transaction_date"].between(TEST_START, TEST_END)) &
    (tx_clean["store_id"].isin(control_stores + treatment_stores))
]

test_gmv = (
    test_tx
    .groupby(["store_id", "year_week"])["total_amount"]
    .sum()
    .reset_index()
    .merge(test_stores_clean, on="store_id")
)

# GMV promedio semanal por tienda
weekly_avg = test_gmv.groupby(["store_id", "variant"])["total_amount"].mean().reset_index()

c_gmv = weekly_avg[weekly_avg["variant"]=="CONTROL"]["total_amount"]
t_gmv = weekly_avg[weekly_avg["variant"]=="TREATMENT"]["total_amount"]

# T-test resultado GMV
stat, pval = stats.ttest_ind(t_gmv, c_gmv)
ci = stats.t.interval(0.95, len(t_gmv)-1,
                       loc=t_gmv.mean() - c_gmv.mean(),
                       scale=stats.sem(t_gmv - c_gmv.values[:len(t_gmv)] if len(c_gmv)>=len(t_gmv) else t_gmv))
diff_abs  = t_gmv.mean() - c_gmv.mean()
lift      = diff_abs / c_gmv.mean() * 100

print(f"\n[AB] === RESULTADOS DEL TEST ===")
print(f"[AB] GMV promedio CONTROL:   ${c_gmv.mean():,.2f}/semana/tienda")
print(f"[AB] GMV promedio TREATMENT: ${t_gmv.mean():,.2f}/semana/tienda")
print(f"[AB] Diferencia absoluta:    ${diff_abs:,.2f}")
print(f"[AB] Lift relativo:          {lift:.1f}%")
print(f"[AB] t-statistic:            {stat:.3f}")
print(f"[AB] p-value:                {pval:.4f}")
print(f"[AB] IC 95%:                 [{ci[0]:,.2f}, {ci[1]:,.2f}]")
significant = "SÍ (p < 0.05)" if pval < 0.05 else f"NO (p = {pval:.3f} > 0.05)"
print(f"[AB] ¿Significativo?          {significant}")

# 4. Ticket y frecuencia
ticket_freq = (
    test_tx
    .merge(test_stores_clean, on="store_id")
    .groupby(["store_id", "variant"])
    .agg(
        avg_ticket=("total_amount", "mean"),
        num_tx=("transaction_id", "count")
    )
    .reset_index()
)
c_ticket = ticket_freq[ticket_freq["variant"]=="CONTROL"]["avg_ticket"]
t_ticket = ticket_freq[ticket_freq["variant"]=="TREATMENT"]["avg_ticket"]
c_freq   = ticket_freq[ticket_freq["variant"]=="CONTROL"]["num_tx"]
t_freq   = ticket_freq[ticket_freq["variant"]=="TREATMENT"]["num_tx"]

print(f"[AB] Ticket CONTROL: ${c_ticket.mean():.2f} | TREATMENT: ${t_ticket.mean():.2f}")
print(f"[AB] Tx/tienda CONTROL: {c_freq.mean():.0f} | TREATMENT: {t_freq.mean():.0f}")

# 5. Visualización del A/B test
fig, axes = plt.subplots(1, 3, figsize=(15, 6))

# GMV semanal promedio
groups     = ["CONTROL", "TREATMENT"]
gmv_means  = [c_gmv.mean(), t_gmv.mean()]
gmv_errs   = [c_gmv.std(), t_gmv.std()]
bar_colors = [WALMART_GRAY, WALMART_BLUE]

bars = axes[0].bar(groups, gmv_means, color=bar_colors,
                   yerr=gmv_errs, capsize=5, width=0.5)
axes[0].set_title(f"GMV Semanal Promedio por Tienda\np-value: {pval:.3f} | Lift: {lift:.1f}%",
                  fontsize=11, fontweight="bold")
axes[0].set_ylabel("GMV Promedio ($/semana/tienda)", fontsize=9)
for bar, val in zip(bars, gmv_means):
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + gmv_errs[0]*0.1,
                 f"${val:,.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
if pval < 0.05:
    axes[0].text(0.5, max(gmv_means)*1.05, "*", ha="center", fontsize=20, color=WALMART_GREEN)

# Ticket promedio
tkt_means = [c_ticket.mean(), t_ticket.mean()]
bars2 = axes[1].bar(groups, tkt_means, color=bar_colors, width=0.5)
axes[1].set_title("Ticket Promedio por Tienda", fontsize=11, fontweight="bold")
axes[1].set_ylabel("Ticket Promedio ($)", fontsize=9)
for bar, val in zip(bars2, tkt_means):
    axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"${val:.2f}", ha="center", va="bottom", fontsize=10)

# Frecuencia (# transacciones)
freq_means = [c_freq.mean(), t_freq.mean()]
bars3 = axes[2].bar(groups, freq_means, color=bar_colors, width=0.5)
axes[2].set_title("Nº Transacciones Totales por Tienda", fontsize=11, fontweight="bold")
axes[2].set_ylabel("Transacciones", fontsize=9)
for bar, val in zip(bars3, freq_means):
    axes[2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{val:.0f}", ha="center", va="bottom", fontsize=10)

fig.suptitle("A/B Test: Nueva Exhibición en Punto de Venta\nSep – Oct 2024 (6 semanas)",
             fontsize=13, fontweight="bold")
plt.tight_layout()
fig.savefig(VIZ_PATH / "ab_test_results.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("[OK] ab_test_results.png")

# Guardar resultados del A/B para el HTML
ab_results = {
    "control_gmv":   c_gmv.mean(),
    "treatment_gmv": t_gmv.mean(),
    "diff_abs":       diff_abs,
    "lift_pct":       lift,
    "pval":           pval,
    "stat":           stat,
    "ci_low":         ci[0],
    "ci_high":        ci[1],
    "significant":    pval < 0.05,
    "comparable_pre": pval_pre > 0.05,
    "contaminated":   contaminated,
    "n_control":      len(control_stores),
    "n_treatment":    len(treatment_stores),
    "control_ticket": c_ticket.mean(),
    "treatment_ticket": t_ticket.mean(),
    "control_freq":   c_freq.mean(),
    "treatment_freq": t_freq.mean(),
}

# ── Guardar datos de hallazgos clave para el HTML ──
# Formato más sensible a estacionalidad
if len(format_cv) > 0:
    most_seasonal = format_cv.index[0]
    least_seasonal = format_cv.index[-1]
else:
    most_seasonal = "N/A"
    least_seasonal = "N/A"

# Pareto summary
cat_total = items_full.groupby("category")["line_gmv"].sum().sort_values(ascending=False)
cat_total_pct = (cat_total / cat_total.sum() * 100).cumsum()
top_cats_80 = cat_total_pct[cat_total_pct <= 80].index.tolist()

print("\n[INFO] Categorías que concentran el 80% del GMV:")
print(top_cats_80)

print("\n[INFO] Todos los gráficos guardados en bloque3_visualizaciones/")
print("[DONE] Bloque 3 completado.")

# Guardar resumen de resultados como JSON para el HTML
import json
results_summary = {
    "ab_test":         ab_results,
    "top_categories":  top_cats_80,
    "most_seasonal":   most_seasonal,
    "least_seasonal":  least_seasonal,
    "total_tx":        len(tx_clean),
    "total_gmv":       tx_clean["total_amount"].sum(),
    "loyalty_rate":    tx_clean["loyalty_card"].mean() * 100,
    "countries":       sorted(tx_clean["country"].unique().tolist()),
    "formats":         sorted(tx_clean["format"].unique().tolist()),
    "total_gaps":      len(gaps_df) if len(gaps_df) > 0 else 0,
    "total_lost_gmv":  float(gaps_df["lost_gmv"].sum()) if len(gaps_df) > 0 else 0,
}

with open("bloque3_resultados.json", "w", encoding="utf-8") as f:
    # Convertir numpy types
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return obj
    json.dump(results_summary, f, default=convert, indent=2, ensure_ascii=False)
print("[OK] bloque3_resultados.json guardado.")
