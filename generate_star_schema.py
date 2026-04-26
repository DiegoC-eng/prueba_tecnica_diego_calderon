"""
Generador del diagrama Star Schema para bloque2_modelo.pdf
Autor: Diego Alberto Calderón
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

WAL_BLUE  = '#0053e2'
WAL_SPARK = '#ffc220'
WAL_GRAY  = '#74767c'
WAL_LIGHT = '#e8f0fd'
WAL_BGRAY = '#f5f5f5'

fig, ax = plt.subplots(1, 1, figsize=(18, 13))
ax.set_xlim(0, 18)
ax.set_ylim(0, 13)
ax.axis('off')
fig.patch.set_facecolor('white')

def draw_table(ax, x, y, w, h, title, fields, header_color, title_color='white', field_color='#1a1a2e', is_fact=False):
    # Header
    header = FancyBboxPatch((x, y + h - 0.55), w, 0.55,
                            boxstyle='round,pad=0.05',
                            facecolor=header_color, edgecolor='white', linewidth=2)
    ax.add_patch(header)
    ax.text(x + w/2, y + h - 0.275, title,
            ha='center', va='center', fontsize=9.5, fontweight='bold',
            color=title_color)
    # Body
    body = FancyBboxPatch((x, y), w, h - 0.55,
                          boxstyle='round,pad=0.05',
                          facecolor=WAL_LIGHT if not is_fact else '#fff7e0',
                          edgecolor=header_color, linewidth=1.5)
    ax.add_patch(body)
    row_h = (h - 0.55) / max(len(fields), 1)
    for i, field in enumerate(fields):
        fy = y + (h - 0.55) - (i + 0.5) * row_h
        prefix = '🔑 ' if '(PK)' in field else ('  └ ' if '(FK)' in field else '   ')
        text = field.replace('(PK)', '').replace('(FK)', '').strip()
        ax.text(x + 0.12, fy, prefix + text,
                ha='left', va='center', fontsize=7.5,
                color='#1a1a2e',
                fontfamily='monospace')

# ============================================================
# FACT TABLE: fact_sales (centro)
# ============================================================
fact_fields = [
    'fact_sale_id (PK)',
    'transaction_id',
    'date_id (FK)',
    'store_id (FK)',
    'product_id (FK)',
    'customer_id (FK — NULLABLE)',
    'promo_id (FK — NULLABLE)',
    'quantity',
    'unit_price',
    'unit_cost',
    'gross_revenue',
    'gross_margin',
    'was_on_promo',
    'is_returned',
    '_loaded_at',
]
draw_table(ax, 6.2, 3.5, 5.6, 7.8,
           '★ fact_sales  (GRANULARIDAD: îDEM × DÍA × TIENDA)',
           fact_fields, WAL_SPARK, title_color='#1a1a2e', is_fact=True)

# ============================================================
# DIM TABLES
# ============================================================
# dim_date (arriba centro)
draw_table(ax, 6.5, 11.3, 5, 1.6,
           'dim_date',
           ['date_id (PK)', 'day_of_week', 'week | month | quarter | year',
            'is_weekend | is_holiday | fiscal_period'],
           WAL_BLUE)

# dim_store (izquierda)
draw_table(ax, 0.2, 5.5, 4.8, 5.0,
           'dim_store',
           ['store_id (PK)', 'store_name', 'country | city',
            'format | region', 'size_sqm', 'opening_date',
            'is_comparable ← pre-computed flag'],
           WAL_BLUE)

# dim_product (derecha)
draw_table(ax, 13.0, 5.5, 4.7, 4.5,
           'dim_product',
           ['product_id (PK)', 'item_name | brand',
            'category | department', 'vendor_id (FK)',
            'unit_cost'],
           WAL_BLUE)

# dim_customer (abajo izquierda)
draw_table(ax, 0.2, 0.2, 4.8, 4.5,
           'dim_customer  (SCD Tipo 1)',
           ['customer_id (PK)', 'first_transaction_date',
            'cohort_month', 'total_lifetime_txns',
            'is_identified  ← FALSE si ANON'],
           WAL_BLUE)

# dim_vendor (abajo derecha)
draw_table(ax, 13.0, 0.2, 4.7, 3.5,
           'dim_vendor',
           ['vendor_id (PK)', 'vendor_name', 'country',
            'tier  (A / B / C)', 'is_shared_catalog'],
           WAL_BLUE)

# dim_promotion (abajo centro)
draw_table(ax, 6.5, 0.2, 5.0, 3.2,
           'dim_promotion',
           ['promo_id (PK)', 'store_id | promo_name',
            'variant (CONTROL/TREATMENT)',
            'promo_type | start_date | end_date'],
           WAL_BLUE)

# ============================================================
# FLECHAS FK
# ============================================================
arrow_props = dict(arrowstyle='->', color=WAL_GRAY, lw=1.8)

def arrow(ax, x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=WAL_GRAY, lw=1.8,
                                connectionstyle='arc3,rad=0.0'))

# fact_sales -> dim_date (arriba)
arrow(ax, 9.0, 11.3, 9.0, 11.3)
ax.annotate('', xy=(9.0, 11.3), xytext=(9.0, 11.3),
            arrowprops=dict(arrowstyle='->', color=WAL_GRAY, lw=1.5))
# Flechas simples
ax.annotate('', xy=(9.0, 11.3), xytext=(9.0, 11.3))

# Usamos matplotlib.pyplot.annotate manualmente
connections = [
    # (x_fact_edge, y_fact_edge, x_dim_edge, y_dim_edge)
    (9.0,  11.3,  9.0, 12.9),   # -> dim_date
    (6.2,   7.5,  5.0,  8.0),   # -> dim_store
    (11.8,  7.5, 13.0,  7.5),   # -> dim_product
    (6.2,   5.0,  5.0,  3.0),   # -> dim_customer
    (11.8,  5.0, 13.0,  3.0),   # -> dim_vendor
    (9.0,   3.5,  9.0,  3.4),   # -> dim_promotion
]
for x1, y1, x2, y2 in connections:
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle='->', color=WAL_GRAY, lw=1.8,
                    connectionstyle='arc3,rad=0.0'
                ))

# Título
ax.text(9.0, 12.75, 'Star Schema — Retail Multiformato Centroamérica',
        ha='center', va='center', fontsize=14, fontweight='bold', color=WAL_BLUE)
ax.text(9.0, 12.45, 'BigQuery • Granularidad: Ítem de Transacción • Particionado por date_id',
        ha='center', va='center', fontsize=9, color=WAL_GRAY)

plt.tight_layout(pad=0.5)
plt.savefig('bloque3_visualizaciones/star_schema_diagram.png', dpi=180, bbox_inches='tight',
            facecolor='white')
plt.savefig('bloque2_modelo_diagram.png', dpi=180, bbox_inches='tight', facecolor='white')
print('Diagrama guardado: bloque2_modelo_diagram.png')
print('Copia en: bloque3_visualizaciones/star_schema_diagram.png')
