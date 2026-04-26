# Bloque 3 — Análisis Exploratorio + Experimentación A/B

**Autor:** Diego Alberto Calderón Calderón  
**Dataset:** Cadena Retail Multiformato Centroamérica | Ene 2024 – Jun 2025  
**Herramientas:** Python 3.13, Pandas 3.0, Matplotlib, Seaborn, SciPy  
**Transacciones analizadas (post-limpieza):** 171,275  
**GMV total analizado:** ~$47.6M  

> Las visualizaciones referenciadas se encuentran en `bloque3_visualizaciones/`.

---

## PARTE A — ANÁLISIS EXPLORATORIO

---

### Pregunta 1 — Estacionalidad por Formato

*¿Cómo evoluciona el GMV semanal por formato? ¿Qué formato es más sens ible a la estacionalidad?*  
🖼️ Ver: `bloque3_visualizaciones/p1_estacionalidad_formato.png`

#### Hallazgos

**HIPERMERCADO** es el formato con mayor GMV absoluto semanal y también el más volátil. Concentra picos pronunciados en diciembre 2024 y semana santa (abril 2024), consistentes con comportamiento de “compra de canasta completa” en fechas de alto tráfico.

**SUPERMERCADO** muestra la curva más estable, con variación semanal baja. Esto sugiere que sus clientes tienen patrones de compra regulares (compra semanal de alimentos) menos afectados por estacionalidad.

**DESCUENTO** muestra sensibilidad al inicio de mes (días de pago en Centroamérica: 1 y 15), con caídas notables a mediados de mes.

**EXPRESS** tiene el GMV más bajo y estable, coherente con su modelo de tienda de conveniencia y ticket pequeño.

#### 3 Picos Identificados
| Pico | Período | Hipótesis |
|---|---|---|
| 1 | Semana del 23-dic-2024 | Navidad + aguinaldos en CA: compras de canasta festiva |
| 2 | Semana del 5-abr-2024 | Semana Santa: acopio de alimentos y bebidas |
| 3 | Semana del 29-oct-2024 | Pre-noviembre: inicio de temporada escolar Q1 2025 en algunos países |

#### 3 Caídas Identificadas
| Caída | Período | Hipótesis |
|---|---|---|
| 1 | Mid-enero 2024 | Post-gasto navideño: contracción de consumo |
| 2 | Julio 2024 | Fin de año escolar + vacaciones: migración a formatos más baratos |
| 3 | Semana del 13-may-2025 | Posible efecto de mayo (inicio de lluvias): menor movilidad |

---

### Pregunta 2 — Pareto de Categorías por Formato

*¿Qué categorías concentran el 80% del GMV? ¿Son las mismas en HIPERMERCADO y DESCUENTO?*  
🖼️ Ver: `bloque3_visualizaciones/p2_pareto_categorias.png`

#### Hallazgos

**HIPERMERCADO:** Las categorías líder son **Electrónica, Hogar y Alimentos**. Tres categorías concentran ~75% del GMV. El comprador de hipermercado viene por productos de mayor valor y hace compra de despensa completa.

**SUPERMERCADO:** **Alimentos y Bebidas** dominan ampliamente (≥65% del GMV). Perfil claro: comprador semanal de alimentos frescos y empacados.

**DESCUENTO:** **Alimentos y Limpieza** con tickets más pequeños. El comprador de descuento es más sensible al precio y prioriza productos de primera necesidad.

**EXPRESS:** **Bebidas, Cuidado Personal y Alimentos** — compras de urgencia/conveniencia. Alta penetración de bebidas fritas sugiere trfico de tránsito.

#### Implicación para el negocio
Las categorías líder **NO son las mismas** entre formatos, lo que valida la estrategia multiformato. Un quiebre de stock en Electrónica en un HIPERMERCADO tiene5x mayor que el mismo quiebre en un DESCUENTO. El surtido y los KPIs deben ser **format-specific**.

---

### Pregunta 3 — Cohortes de Lealtad

*¿Las cohortes recientes retienen mejor? ¿El ticket crece con el tiempo?*  
🖼️ Ver: `bloque3_visualizaciones/p3_cohortes_lealtad.png`

#### Hallazgos

**Retención M+1:** Las cohortes de Ene–Mar 2024 muestran retención M+1 en el rango de **30-38%**. Las cohortes más recientes (Oct–Nov 2024) muestran retención levemente inferior, lo que puede indicar que el programa de lealtad está atrayendo nuevos clientes con menor intención de recompra, o que el efecto del programa se diluye con el tiempo.

**Mayor caída:** El paso de M+1 a M+2 es consistentemente la mayor caída de retención en todas las cohortes (≡15 puntos porcentuales). Esto indica que el programa de lealtad activa la segunda compra pero no logra construir hábito.

**Ticket a lo largo del tiempo:** Los clientes retenidos muestran una **leve tendencia creciente** en ticket promedio en M+3 y M+6 vs. M+0. Esto valida que los clientes leales son más valiosos, no solo más frecuentes.

**Recomendación:** Diseñar una intervención específica para el período M+1 a M+2 (ej: cupon personalizado en la 3ra semana post-segunda compra) para frenar la caída.

---

### Pregunta 4 — Quiebres de Stock y su Impacto

*¿Hay categorías o proveedores con quiebres sistemáticos?*  
🖼️ Ver: `bloque3_visualizaciones/p4_quiebres_stock.png`

#### Hallazgos (proxy de OOS: SKUs con rotación <40% del promedio)

**Electrónica** y **Juguetes** concentran el mayor GMV en riesgo estimado, consistente con su alta estacionalidad (picos de Navidad) y probable desconfiguración del surtido en períodos valle.

**Ropa** y **Cuidado Personal** tienen el mayor número de SKU-tienda con baja rotación, lo que sugiere problemas de surtido (demasiados SKUs de bajo movimiento) más que quiebres de stock propiamente dichos.

**Implicación:** El problema parece ser mixto:
- **Demanda** en Electrónica/Juguetes (quiebres reales en temporada alta)
- **Surtido excesivo** en Ropa/Cuidado Personal (SKUs de muy baja rotación que ocupan espacio sin contribuir al GMV)

---

### Pregunta 5 — Hallazgo Libre: Adopción de Pago Digital por País

🖼️ Ver: `bloque3_visualizaciones/p5_metodos_pago_pais.png`

#### Hallazgo

Existe una **brecha significativa en la adopción de pagos digitales** entre países:

- **Costa Rica (CR)** lidera con la mayor penetración de DIGITAL (~17%) y CARD (~55%), reflejo de la mayor penetración bancaria del país.
- **Honduras (HN) y Nicaragua (NI)** mantienen la mayor proporción de CASH (~40%), consistente con sus niveles de bancarización más bajos.
- **Guatemala (GT) y El Salvador (SV)** están en posición intermedia, con CARD como método dominante.

#### Impacto para el negocio

1. **Eficiencia operativa:** Las tiendas con alto uso de efectivo tienen mayor costo de manejo de caja, mayor riesgo de robo y mayor tiempo de checkout. Una estrategia de digitalización en HN/NI podría reducir costos operativos.
2. **Oportunidad de lealtad:** Los pagos digitales son trazables. Un programa que incentive pago digital simultáneamente con la tarjeta de lealtad podría aumentar la identificación de clientes del ~40% actual a >55%.
3. **Dato accionable:** La cadena podría negociar acuerdos con billeteras móviles (Tigo Money, Nequi) para mercados de baja bancarización.

---

## PARTE B — A/B TEST: Nueva Exhibición en Punto de Venta

🖼️ Ver: `bloque3_visualizaciones/ab_test_resultado.png`

**Escenario:** Test de nueva estrategia de exhibición. Período: Sep–Oct 2024 (6 semanas).  
**Tiendas excluidas por dual-assignment:** `TIENDA_008`, `TIENDA_037`

---

### 1. Validación del Experimento

| Métrica | CONTROL | TREATMENT |
|---|---|---|
| Número de tiendas | 18 | 20 |
| Tiendas en ambos grupos | 0 (excluidas) | 0 (excluidas) |

Los grupos son razonablemente comparables en tamaño. Sin embargo, **no tenemos información sobre el proceso de randomización**: ¿las tiendas se asignaron aleatoriamente o por conveniencia? Esto es una limitación importante. Idealmente habríamos verificado balance en GMV pre-test, formato y tamaño (m²) mediante un test de balance (p.ej. Mann-Whitney por formato) antes de arrancar el experimento.

---

### 2. Resultado en GMV

| Métrica | Valor |
|---|---|
| GMV promedio semanal CONTROL | **$14,449.72** |
| GMV promedio semanal TREATMENT | **$12,004.98** |
| Diferencia absoluta | **-$2,444.74** |
| Lift relativo | **-16.92%** |
| p-value (Welch t-test) | **0.2424** |
| IC 95% de la diferencia | **[-$6,476, +$1,586]** |
| Estadísticamente significativo (p < 0.05) | **NO** |

---

### 3. Resultado en Ticket y Frecuencia

El resultado negativo (TREATMENT < CONTROL) no es significativo estadísticamente, pero el intervalo de confianza es amplio y cruza el cero, lo que indica **alta variabilidad entre tiendas**. Es probable que el efecto sea heterogéneo por formato: la nueva exhibición podría funcionar en hipermercados pero no en express, promediando hacia cero o negativo.

Para determinar si el efecto viene de ticket o frecuencia se requeriría un análisis adicional por formato, pero con la información disponible el veredicto es: **no hay evidencia de impacto positivo en GMV**.

---

### 4. Decisión de Negocio

**No implementar** la nueva exhibición en todas las tiendas con los datos actuales.

**Justificación:**
- El lift observado es **negativo (-16.92%)**, aunque no significativo. En ausencia de evidencia positiva, el principio de precaución aplica.
- El intervalo de confianza incluye el cero, pero también pérdidas de hasta -$6,476/semana/tienda — un riesgo inaceptable a escala de 40 tiendas.
- El p-value de 0.2424 indica que NO podemos rechazar la hipótesis nula (sin efecto).

**Si el p-value fuera 0.08:**
Seguiría sin implementar a toda la red, pero extendería el test 4 semanas adicionales para aumentar el poder estadístico. Un p=0.08 con un lift negativo sería incluso más preocupante — estaría rozando la significancia en la dirección EQUIVOCADA.

**Próximos pasos sugeridos:**
1. Hacer un análisis de heterogeneidad del efecto por formato (HIPERMERCADO vs EXPRESS).
2. Verificar si la asignación fue realmente aleatoria o si hay sesgo de selección.
3. Evaluar si 6 semanas son suficientes (con 38 tiendas el poder estadístico para detectar un lift del 10% puede ser insuficiente).
4. Calcular el MDE (Minimum Detectable Effect) con el presupuesto de tiendas disponible antes del próximo experimento.
