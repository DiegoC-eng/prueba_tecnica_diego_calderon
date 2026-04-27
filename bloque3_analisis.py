"""
Bloque 3 — Análisis Exploratorio + A/B Test
Autor: Diego Alberto Calderón Calderón
Dataset: Cadena Retail Multiformato Centroamérica (Ene 2024 – Jun 2025)

Ejecución: .venv/Scripts/python.exe bloque3_analisis.py
Outputs: bloque3_visualizaciones/ (PNG exports)
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from scipy import stats
import warnings
import os

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================
DATA_DIR = r'C:\Users\d0c00v5\Downloads\Datasets_extracted'
OUT_DIR = 'bloque3_visualizaciones'
os.makedirs(OUT_DIR, exist_ok=True)

# Colores Walmart
WAL_BLUE  = '#0053e2'
WAL_SPARK = '#ffc220'
WAL_RED   = '#ea1100'
WAL_GREEN = '#2a8703'
WAL_GRAY  = '#74767c'
FORMAT_COLORS = {
    'HIPERMERCADO': WAL_BLUE,
    'SUPERMERCADO': WAL_SPARK,
    'DESCUENTO':    WAL_RED,
    'EXPRESS':      WAL_GREEN,
}

plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor':   'white',
    'axes.grid':        True,
    'grid.alpha':       0.3,
    'font.size':        10,
    'axes.titlesize':   13,
    'axes.labelsize':   11,
})

# ============================================================
# CARGA
# ============================================================
print('[1/7] Cargando datos...')
txn   = pd.read_csv(f'{DATA_DIR}/transactions.csv', parse_dates=['transaction_date'])
items = pd.read_csv(f'{DATA_DIR}/transaction_items.csv')
stores= pd.read_csv(f'{DATA_DIR}/stores.csv', parse_dates=['opening_date'])
prods = pd.read_csv(f'{DATA_DIR}/products.csv')
promos= pd.read_csv(f'{DATA_DIR}/store_promotions.csv', parse_dates=['start_date','end_date'])

# Filtros de calidad (bloque0)
txn = txn[(txn['total_amount'] > 0) & (txn['status'] == 'COMPLETED')]
txn = txn.merge(stores[['store_id','opening_date']], on='store_id', how='left')
txn = txn[txn['transaction_date'] >= txn['opening_date']]  # excluir pre-apertura
txn = txn.drop(columns=['opening_date'])

# Join base
base = txn.merge(stores, on='store_id', how='left')
base = base.merge(
    items.merge(prods[['item_id','category','cost']], on='item_id', how='left'),
    on='transaction_id', how='left'
)
base['revenue'] = base['quantity'] * base['unit_price']

print(f'   Transacciones limpias: {len(txn):,}')

# ============================================================
# PREGUNTA 1 — ESTACIONALIDAD POR FORMATO
# ============================================================
print('[2/7] P1 — Estacionalidad por formato...')

base['week'] = base['transaction_date'].dt.to_period('W').apply(lambda r: r.start_time)
weekly = (
    base.groupby(['week', 'format'])['revenue']
    .sum()
    .reset_index()
    .rename(columns={'revenue': 'gmv'})
)

fig, ax = plt.subplots(figsize=(14, 6))
for fmt, color in FORMAT_COLORS.items():
    df_f = weekly[weekly['format'] == fmt].sort_values('week')
    ax.plot(df_f['week'], df_f['gmv'] / 1e3, label=fmt, color=color, linewidth=2)

ax.set_title('GMV Semanal por Formato de Tienda (Ene 2024 – Jun 2025)', fontweight='bold')
ax.set_xlabel('Semana')
ax.set_ylabel('GMV (miles $)')
ax.legend(title='Formato', loc='upper left')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}K'))
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/p1_estacionalidad_formato.png', dpi=150, bbox_inches='tight')
plt.close()
print('   Guardado: p1_estacionalidad_formato.png')

# ============================================================
# PREGUNTA 2 — PARETO DE CATEGORÍAS POR FORMATO
# ============================================================
print('[3/7] P2 — Pareto de categorías por formato...')

cat_fmt = (
    base.groupby(['format', 'category'])['revenue']
    .sum()
    .reset_index()
    .rename(columns={'revenue': 'gmv'})
)

formats = sorted(cat_fmt['format'].unique())
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
axes = axes.flatten()

for idx, fmt in enumerate(formats):
    ax = axes[idx]
    df_f = cat_fmt[cat_fmt['format'] == fmt].sort_values('gmv', ascending=False)
    total = df_f['gmv'].sum()
    df_f['pct'] = df_f['gmv'] / total * 100
    df_f['cum_pct'] = df_f['pct'].cumsum()

    bars = ax.bar(df_f['category'], df_f['pct'],
                  color=FORMAT_COLORS[fmt], alpha=0.8, edgecolor='white')
    ax2 = ax.twinx()
    ax2.plot(df_f['category'], df_f['cum_pct'], 'o-',
             color=WAL_GRAY, linewidth=2, markersize=6)
    ax2.axhline(80, color=WAL_RED, linestyle='--', linewidth=1, alpha=0.7)
    ax2.set_ylabel('% Acumulado', color=WAL_GRAY)
    ax2.set_ylim(0, 115)

    ax.set_title(f'{fmt}', fontweight='bold')
    ax.set_ylabel('% del GMV')
    ax.set_xlabel('')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=40, ha='right')

fig.suptitle('Pareto de Categorías por Formato (% GMV)', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/p2_pareto_categorias.png', dpi=150, bbox_inches='tight')
plt.close()
print('   Guardado: p2_pareto_categorias.png')

# ============================================================
# PREGUNTA 3 — COHORTES DE LEALTAD
# ============================================================
print('[4/7] P3 — Cohortes de lealtad...')

loyalty_txn = txn[(txn['loyalty_card'] == True) & (txn['customer_id'].notna())].copy()
loyalty_txn['month'] = loyalty_txn['transaction_date'].dt.to_period('M')

primera = (
    loyalty_txn.groupby('customer_id')['month']
    .min()
    .reset_index()
    .rename(columns={'month': 'cohort'})
)

loyalty_txn = loyalty_txn.merge(primera, on='customer_id', how='left')
loyalty_txn['mes_rel'] = (
    loyalty_txn['month'].dt.to_timestamp() - loyalty_txn['cohort'].dt.to_timestamp()
).dt.days // 30

cohort_size = primera.groupby('cohort')['customer_id'].nunique()
ret_matrix = (
    loyalty_txn.groupby(['cohort', 'mes_rel'])['customer_id']
    .nunique()
    .unstack(fill_value=0)
)
ret_pct = ret_matrix.divide(cohort_size, axis=0) * 100

# Solo meses 0-6 y cohortes con suficiente historia
ret_pct_plot = ret_pct[[c for c in range(0, 7) if c in ret_pct.columns]].iloc[:-2]

fig, ax = plt.subplots(figsize=(12, 7))
mask = ret_pct_plot == 0
sns.heatmap(
    ret_pct_plot,
    annot=True, fmt='.0f', cmap='Blues',
    mask=mask, linewidths=0.5,
    cbar_kws={'label': '% Retención'},
    ax=ax
)
ax.set_title('Retención de Cohortes — Clientes con Tarjeta de Lealtad (%)', fontweight='bold')
ax.set_xlabel('Mes Relativo desde Primera Compra')
ax.set_ylabel('Cohorte (Mes de Primera Compra)')
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/p3_cohortes_lealtad.png', dpi=150, bbox_inches='tight')
plt.close()
print('   Guardado: p3_cohortes_lealtad.png')

# ============================================================
# PREGUNTA 4 — QUIEBRES DE STOCK
# ============================================================
print('[5/7] P4 — Quiebres de stock (simulado con pandas gaps)...')

# Detectar gaps por tienda-ítem (items con histórico mínimo de 7 días)
sales_daily = (
    base.groupby(['store_id', 'item_id', 'category',
                  base['transaction_date'].dt.date.rename('fecha')])
    ['revenue'].sum().reset_index()
)

# Simplificado: contar pares tienda-ítem con baja rotación (proxy de OOS)
rotacion = (
    base.groupby(['store_id', 'item_id', 'category'])
    .agg(
        dias_con_venta=('transaction_date', 'nunique'),
        gmv_total=('revenue', 'sum')
    )
    .reset_index()
)
prom = rotacion['dias_con_venta'].mean()
oss_proxy = rotacion[rotacion['dias_con_venta'] < prom * 0.4].copy()
oss_by_cat = oss_proxy.groupby('category').agg(
    sku_oos=('item_id', 'count'),
    gmv_perdido_est=('gmv_total', 'sum')
).reset_index().sort_values('gmv_perdido_est', ascending=True)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
ax1.barh(oss_by_cat['category'], oss_by_cat['sku_oos'],
         color=WAL_RED, alpha=0.8)
ax1.set_title('SKUs con Baja Rotación por Categoría', fontweight='bold')
ax1.set_xlabel('Número de SKU-Tienda')

ax2.barh(oss_by_cat['category'],
         oss_by_cat['gmv_perdido_est'] / 1e3,
         color=WAL_SPARK, alpha=0.9, edgecolor='#b38800')
ax2.set_title('GMV en Riesgo por Categoría (proxy OOS)', fontweight='bold')
ax2.set_xlabel('GMV en riesgo (miles $)')
ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}K'))

plt.suptitle('Diagnóstico de Quiebres de Stock Estimados', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/p4_quiebres_stock.png', dpi=150, bbox_inches='tight')
plt.close()
print('   Guardado: p4_quiebres_stock.png')

# ============================================================
# PREGUNTA 5 — HALLAZGO LIBRE: MÉTODOS DE PAGO POR PAÍS
# ============================================================
print('[6/7] P5 — Hallazgo libre: métodos de pago por país...')

payment_country = (
    txn.merge(stores[['store_id', 'country']], on='store_id', how='left')
    .groupby(['country', 'payment_method'])
    .size()
    .unstack(fill_value=0)
)
payment_pct = payment_country.div(payment_country.sum(axis=1), axis=0) * 100

fig, ax = plt.subplots(figsize=(10, 5))
payment_pct.plot(
    kind='bar', ax=ax, stacked=True,
    color=[WAL_BLUE, WAL_SPARK, WAL_GREEN],
    edgecolor='white', width=0.6
)
ax.set_title('Distribución de Métodos de Pago por País (%)', fontweight='bold')
ax.set_xlabel('País')
ax.set_ylabel('% de Transacciones')
ax.legend(title='Método de Pago', bbox_to_anchor=(1.02, 1), loc='upper left')
plt.xticks(rotation=0)
for bar in ax.patches:
    height = bar.get_height()
    if height > 5:
        ax.text(
            bar.get_x() + bar.get_width() / 2.,
            bar.get_y() + height / 2.,
            f'{height:.0f}%',
            ha='center', va='center',
            fontsize=9, color='white', fontweight='bold'
        )
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/p5_metodos_pago_pais.png', dpi=150, bbox_inches='tight')
plt.close()
print('   Guardado: p5_metodos_pago_pais.png')

# ============================================================
# PARTE B — A/B TEST
# ============================================================
print('[7/7] AB Test — Exhibición punto de venta...')

# Tiendas excluidas por dual-assignment (bloque0)
EXCLUIR = {'TIENDA_008', 'TIENDA_037'}

# Período del test: Sep–Oct 2024 (6 semanas)
ab_start = pd.Timestamp('2024-09-01')
ab_end   = pd.Timestamp('2024-10-13')

# Asignar variante a cada tienda
store_variant = (
    promos[~promos['store_id'].isin(EXCLUIR)]
    [['store_id', 'variant']]
    .drop_duplicates(subset='store_id', keep='first')
)

# Transacciones en el período del test
ab_txn = (
    txn[
        (txn['transaction_date'] >= ab_start) &
        (txn['transaction_date'] <= ab_end) &
        (~txn['store_id'].isin(EXCLUIR))
    ]
    .merge(stores[['store_id', 'format', 'size_sqm', 'country']], on='store_id', how='left')
    .merge(store_variant, on='store_id', how='inner')
)

# GMV semanal por tienda
ab_txn['week'] = ab_txn['transaction_date'].dt.to_period('W')
weekly_ab = (
    ab_txn.groupby(['store_id', 'variant', 'week'])
    .agg(gmv=('total_amount', 'sum'), n_txn=('transaction_id', 'count'))
    .reset_index()
)

# Promedio semanal por tienda-variante
store_avg = (
    weekly_ab.groupby(['store_id', 'variant'])
    .agg(avg_gmv_week=('gmv', 'mean'), avg_txn_week=('n_txn', 'mean'))
    .reset_index()
)

control   = store_avg[store_avg['variant'] == 'CONTROL']['avg_gmv_week']
treatment = store_avg[store_avg['variant'] == 'TREATMENT']['avg_gmv_week']

# t-test
t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)
mean_ctrl  = control.mean()
mean_treat = treatment.mean()
diff_abs   = mean_treat - mean_ctrl
lift_pct   = diff_abs / mean_ctrl * 100

# IC 95% de la diferencia
n1, n2 = len(treatment), len(control)
se = np.sqrt(treatment.var()/n1 + control.var()/n2)
ci_low  = diff_abs - 1.96 * se
ci_high = diff_abs + 1.96 * se

print('\n========== RESULTADOS A/B TEST ==========')
print(f'Control stores  : {n2}')
print(f'Treatment stores: {n1}')
print(f'GMV prom. semanal CONTROL   : ${mean_ctrl:,.2f}')
print(f'GMV prom. semanal TREATMENT : ${mean_treat:,.2f}')
print(f'Diferencia absoluta         : ${diff_abs:,.2f}')
print(f'Lift relativo               : {lift_pct:.2f}%')
print(f'p-value (Welch t-test)      : {p_value:.4f}')
print(f'IC 95%                      : [${ci_low:,.2f}, ${ci_high:,.2f}]')
print(f'Significativo (p<0.05)      : {"SÍ" if p_value < 0.05 else "NO"}')
print('=========================================')

# Guardar resultados en un archivo para el notebook
with open('ab_test_results.txt', 'w', encoding='utf-8') as f:
    f.write(f'n_control={n2}\n')
    f.write(f'n_treatment={n1}\n')
    f.write(f'mean_control={mean_ctrl:.4f}\n')
    f.write(f'mean_treatment={mean_treat:.4f}\n')
    f.write(f'diff_abs={diff_abs:.4f}\n')
    f.write(f'lift_pct={lift_pct:.4f}\n')
    f.write(f'p_value={p_value:.6f}\n')
    f.write(f'ci_low={ci_low:.4f}\n')
    f.write(f'ci_high={ci_high:.4f}\n')

# Visualización A/B
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

# Box plot
plot_data = store_avg.copy()
plot_data['variant_label'] = plot_data['variant'].map({
    'CONTROL': f'CONTROL\n(n={n2})',
    'TREATMENT': f'TREATMENT\n(n={n1})'
})

for var, color, ax_plot in [
    ('CONTROL', WAL_GRAY, ax1),
    ('TREATMENT', WAL_BLUE, ax1)
]:
    d = store_avg[store_avg['variant'] == var]['avg_gmv_week']
    ax1.boxplot(
        d, positions=[0 if var == 'CONTROL' else 1],
        patch_artist=True,
        boxprops=dict(facecolor=color, alpha=0.7),
        medianprops=dict(color='white', linewidth=2),
        widths=0.4
    )

ax1.set_xticks([0, 1])
ax1.set_xticklabels([f'CONTROL\nn={n2}', f'TREATMENT\nn={n1}'])
ax1.set_title('GMV Prom. Semanal por Tienda', fontweight='bold')
ax1.set_ylabel('GMV promedio semanal ($)')
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))

# Texto de resultados
results_text = (
    f'Diferencia: ${diff_abs:,.0f}\n'
    f'Lift: {lift_pct:.1f}%\n'
    f'p-value: {p_value:.4f}\n'
    f'IC 95%: [${ci_low:,.0f}, ${ci_high:,.0f}]\n'
    f'Significativo: {"SÍ" if p_value < 0.05 else "NO"}'
)
ax2.axis('off')
ax2.text(0.1, 0.5, results_text, transform=ax2.transAxes,
         fontsize=13, verticalalignment='center',
         bbox=dict(boxstyle='round', facecolor=WAL_SPARK, alpha=0.3))
ax2.set_title('Resultados Estadísticos', fontweight='bold')

fig.suptitle('A/B Test — Nueva Exhibición Punto de Venta (Sep–Oct 2024)',
             fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/ab_test_resultado.png', dpi=150, bbox_inches='tight')
plt.close()
print('   Guardado: ab_test_resultado.png')

print('\n[DONE] Todas las visualizaciones generadas en bloque3_visualizaciones/')
