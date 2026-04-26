# Script de exploración y auditoría de datos
# Genera estadísticas para bloque0_auditoria.md

import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = r'C:\Users\d0c00v5\Downloads\Datasets_extracted'

print('=== CARGANDO DATOS ===')
txn = pd.read_csv(f'{DATA_DIR}/transactions.csv', parse_dates=['transaction_date'])
items = pd.read_csv(f'{DATA_DIR}/transaction_items.csv')
stores = pd.read_csv(f'{DATA_DIR}/stores.csv', parse_dates=['opening_date'])
products = pd.read_csv(f'{DATA_DIR}/products.csv')
vendors = pd.read_csv(f'{DATA_DIR}/vendors.csv')
promos = pd.read_csv(f'{DATA_DIR}/store_promotions.csv', parse_dates=['start_date', 'end_date'])

print(f'transactions: {len(txn):,} rows')
print(f'transaction_items: {len(items):,} rows')
print(f'stores: {len(stores):,} rows')
print(f'products: {len(products):,} rows')
print(f'vendors: {len(vendors):,} rows')
print(f'store_promotions: {len(promos):,} rows')

print('\n=== COLUMNAS ===')
for name, df in [('transactions', txn), ('items', items), ('stores', stores), 
                  ('products', products), ('vendors', vendors), ('promos', promos)]:
    print(f'{name}: {list(df.columns)}')

print('\n=== BLOQUE 0: AUDITORÍA ===')

# 1. Completitud: customer_id nulo
null_cust = txn['customer_id'].isna().sum()
total_txn = len(txn)
pct_null_cust = null_cust / total_txn * 100
no_loyalty = (txn['loyalty_card'] == False).sum()
print(f'\n1. COMPLETITUD customer_id')
print(f'   Transacciones sin customer_id: {null_cust:,} ({pct_null_cust:.2f}%)')
print(f'   Transacciones con loyalty_card=FALSE: {no_loyalty:,}')
print(f'   Diferencia: {abs(null_cust - no_loyalty):,}')

# 2. Consistencia: total_amount vs suma de items
print(f'\n2. CONSISTENCIA total_amount')
items_sum = items.groupby('transaction_id').apply(lambda x: (x['unit_price'] * x['quantity']).sum()).reset_index()
items_sum.columns = ['transaction_id', 'calc_total']
merged = txn.merge(items_sum, on='transaction_id', how='left')
merged['diff'] = abs(merged['total_amount'] - merged['calc_total'])
inconsistent = (merged['diff'] > 0.01).sum()  # tolerance for float
print(f'   Transacciones con discrepancia >$0.01: {inconsistent:,}')
if inconsistent > 0:
    print(f'   Diferencia máxima: ${merged["diff"].max():.4f}')
    print(f'   Diferencia promedio: ${merged["diff"].mean():.4f}')

# 3. Unicidad: duplicados en transaction_id
print(f'\n3. UNICIDAD transaction_id')
dupes = txn['transaction_id'].duplicated().sum()
print(f'   transaction_id duplicados: {dupes:,}')
items_dupes = items['transaction_item_id'].duplicated().sum()
print(f'   transaction_item_id duplicados: {items_dupes:,}')

# 4. Validez: total_amount <=0, unit_price=0 sin promo
print(f'\n4. VALIDEZ')
neg_total = (txn['total_amount'] <= 0).sum()
neg_pct = neg_total/total_txn*100
print(f'   total_amount <= 0: {neg_total:,} ({neg_pct:.2f}%)')
zero_price_no_promo = items[(items['unit_price'] == 0) & (items['was_on_promo'] == False)]
print(f'   unit_price=0 con was_on_promo=FALSE: {len(zero_price_no_promo):,}')

# 5. Integridad referencial
print(f'\n5. INTEGRIDAD REFERENCIAL')
stores_in_txn = set(txn['store_id'].unique())
stores_master = set(stores['store_id'].unique())
orphan_stores = stores_in_txn - stores_master
print(f'   store_id en transactions NO en stores: {len(orphan_stores):,}')
vendors_in_prod = set(products['vendor_id'].unique())
vendors_master = set(vendors['vendor_id'].unique())
orphan_vendors = vendors_in_prod - vendors_master
print(f'   vendor_id en products NO en vendors: {len(orphan_vendors):,}')
products_in_items = set(items['item_id'].unique())
products_master = set(products['item_id'].unique())
orphan_products = products_in_items - products_master
print(f'   item_id en transaction_items NO en products: {len(orphan_products):,}')

# 6. Frescura: gaps de días
print(f'\n6. FRESCURA - gaps de tiendas sin transacciones')
date_range = pd.date_range(txn['transaction_date'].min(), txn['transaction_date'].max(), freq='D')
print(f'   Rango de fechas: {txn["transaction_date"].min().date()} a {txn["transaction_date"].max().date()}')
print(f'   Días totales en el período: {len(date_range):,}')
store_daily = txn.groupby(['store_id', 'transaction_date']).size()
stores_with_gaps = []
for store in stores['store_id'].unique():
    store_dates = set(txn[txn['store_id']==store]['transaction_date'].dt.date.unique())
    expected = set(pd.date_range(txn[txn['store_id']==store]['transaction_date'].min(), 
                                  txn[txn['store_id']==store]['transaction_date'].max(), freq='D').date)
    gaps = expected - store_dates
    if len(gaps) > 0:
        stores_with_gaps.append((store, len(gaps)))
print(f'   Tiendas con al menos 1 día sin transacciones: {len(stores_with_gaps):,}')
if stores_with_gaps:
    max_gap_store = max(stores_with_gaps, key=lambda x: x[1])
    print(f'   Tienda con más gaps: {max_gap_store[0]} ({max_gap_store[1]} días)')

# 7. Integridad temporal: txn antes de opening_date
print(f'\n7. INTEGRIDAD TEMPORAL')
txn_store = txn.merge(stores[['store_id','opening_date']], on='store_id', how='left')
early_txn = txn_store[txn_store['transaction_date'] < txn_store['opening_date']]
print(f'   Transacciones ANTES de opening_date: {len(early_txn):,}')

# 8. A/B Test: tiendas en CONTROL y TREATMENT simultáneo
print(f'\n8. A/B TEST INTEGRIDAD')
promos_pivot = promos.groupby('store_id')['variant'].apply(list).reset_index()
both_variants = promos_pivot[promos_pivot['variant'].apply(lambda x: 'CONTROL' in x and 'TREATMENT' in x)]
print(f'   Tiendas asignadas a CONTROL y TREATMENT: {len(both_variants):,}')
if len(both_variants) > 0:
    print(f'   Tiendas afectadas: {list(both_variants["store_id"].values)}')

# Stats generales
print(f'\n=== ESTADÍSTICAS GENERALES ===')
print(f'GMV total: ${txn["total_amount"].sum():,.2f}')
print(f'Ticket promedio: ${txn["total_amount"].mean():.2f}')
print(f'Ticket mediano: ${txn["total_amount"].median():.2f}')
print(f'Países: {sorted(stores["country"].unique())}')
print(f'Formatos: {sorted(stores["format"].unique())}')
print(f'Categorías: {sorted(products["category"].unique())}')
print(f'Métodos de pago: {txn["payment_method"].value_counts().to_dict()}')
print(f'Status transacciones: {txn["status"].value_counts().to_dict()}')
print(f'Tiendas activas: {len(stores):,}')
print(f'Productos únicos: {len(products):,}')
print(f'Proveedores únicos: {len(vendors):,}')
print(f'Transacciones devueltas: {(txn["status"]=="RETURNED").sum():,} ({(txn["status"]=="RETURNED").mean()*100:.2f}%)')
print(f'Uso tarjeta lealtad: {txn["loyalty_card"].mean()*100:.2f}%')

# Distribución por formato
print(f'\nDistribución por formato:')
format_dist = stores.groupby('format').size()
print(format_dist.to_string())

print(f'\nDistribución por país:')
country_dist = stores.groupby('country').size()
print(country_dist.to_string())

print(f'\n=== DONE ===')
