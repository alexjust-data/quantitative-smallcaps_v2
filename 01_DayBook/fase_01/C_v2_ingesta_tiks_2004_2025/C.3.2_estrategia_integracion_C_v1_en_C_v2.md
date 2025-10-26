Me encanta esta estrategia. Te la voy a evaluar con todo el cariño pero también con mala leche técnica, porque este punto es IMPORTANTÍSIMO para todo tu proyecto (y porque aquí, si la cagamos, arruinamos años de histórico o metemos sesgo sin darnos cuenta).

Voy a responder en 5 bloques:

1. Qué problema está resolviendo exactamente esta estrategia
2. Qué hace E0 y por qué es la clave
3. Por qué C_v2_extendido con E0 sí puede reemplazar todo (C_v1 + C_v2)
4. Dónde todavía hay riesgo / cosas que hay que vigilar
5. Qué haría yo ahora mismo

──────────────────

1. El problema real que tienes
   ──────────────────

Tu duda original era:

> “Si descargo usando C_v2 (eventos específicos), ¿eso ya incluye todo lo que cubría C_v1 (info-rich diario RVOL≥2, etc.) o pierdo cosas?”

Respuesta honesta: C_v2 original NO lo incluía todo. Perdías entre un ~30% y 40% de los días que C_v1 sí habría considerado importantes (los días “calientes pero no extremos”: RVOL 3, +18%, $7M, etc.). Esos días son súper operables en small caps, especialmente para setups como VWAP reclaim, late-day fade, bounce after flush… que NO siempre son “parabolic +50% en 5 días”, ni “RVOL 5x”.

Entonces había dos caminos malos:

* camino malo A: mantener 2 pipelines paralelos (uno C_v1 y otro C_v2) → duplicas todo: lógica, auditoría, ingesta, almacenamiento de ticks, DIBs, etiquetas, pesos, dataset ML. Horror de mantenimiento.

* camino malo B: tirar C_v1 y quedarte solo con C_v2 → más limpio pero pierdes histórico de eventos moderados que sí son tradeables y que de hecho son una parte importante de tu edge operativo real.

La propuesta del documento que mostraste (C_v2_extendido con E0) ataca justo eso:

👉 Define un nuevo tipo de evento dentro de C_v2 llamado **E0 = Generic_Info_Rich** que copia EXACTAMENTE el criterio de C_v1.

Y esto, si se hace bien, resuelve el problema de raíz.

──────────────────
2. ¿Qué es E0 y por qué es oro?
──────────────────

E0 es literalmente “recrea C_v1 dentro de C_v2”.

Definición E0 (tal como la planteasteis):

* RVOL(30d) ≥ 2.0
* |%chg día| ≥ 15%
* Dollar volume ≥ $5M
* Precio cierre entre $0.50 y $20
* Ventana temporal = TODO EL DÍA ampliado (premarket 04:00 → afterhours 20:00)

Esto es exactamente tu definición original de info-rich diario, que usamos en 2020-2025 para decidir qué días bajar ticks, construir DIBs, etc.

Entonces:

* Antes: C_v1 decía “bájame ticks de todos los días que cumplen esto”.
* Ahora: C_v2_extendido dice “detecta todos los eventos E0..E13. E0 es justamente eso mismo”.

Traducción: C_v2_extendido incluye E0, y E0 = C_v1.

Matemáticamente:

* Sea S₁ = conjunto de (ticker, day) que C_v1 habría bajado.
* Sea S₂ = conjunto de (ticker, day) que C_v2_extendido marca como evento (E0/E1/E4/E7/E8/E13…).

Si E0 está bien implementado, entonces:
👉 S₁ ⊆ S₂

Eso significa: TODO lo que C_v1 habría querido bajar ticks, C_v2_ext lo va a marcar como evento E0 (o quizá también como otro evento más específico con más prioridad). O sea: no pierdes nada.

──────────────────
3. ¿Entonces puedo tirar C_v1 y quedarme solo con C_v2_extendido?
──────────────────

Si, PERO SOLO si cumples 3 condiciones técnicas:

(1) E0 está implementado literalmente igual que C_v1

* misma fórmula de RVOL (media 30 días excluyendo el día actual, no “rolling incluyéndolo”, no mediana, no volumen regular hours solamente, etc.)
* mismo %chg (usaste abs((close-open)/open), NO abs((close-prev_close)/prev_close) → hay que fijarlo y no cambiarlo)
* mismo dollar_volume (volumen * VWAP intradía/día, no volumen * close si antes usabas VWAP)
* mismos cortes de precio [$0.50, $20] exactos

Si cambias aunque sea un detalle, ya no puedes garantizar la inclusión matemática S₁ ⊆ S₂. Y volveríamos a tener huecos.

(2) Para cada día-ticker donde se dispara E0, generas un “evento descargable” en el catálogo final de eventos, con ventana temporal clara (ej. 04:00→20:00 ese día).

* Esto parece obvio pero es muy importante: si detectas E0 pero luego decides no generar tick-task porque ese mismo día también fue clasificado como E4 “Parabolic Move” y tu código solo guarda el evento prioritario, tienes que asegurarte de que en el registro final QUEDEN las coordenadas temporales de la ventana que cubrirían E0 (es decir, no recortar la ventana sin querer).
* En el diseño que muestras ya lo resolvisteis con prioridad: guardas el evento de máxima prioridad como etiqueta principal, pero añades `also_detected=["E0", ...]`. Eso está MUY BIEN porque preserva que ese día era info-rich genérico aunque lo clasifiques como algo más específico.

(3) El pipeline de bajar ticks (download_trades_unified.py o como lo llames) usa ese catálogo extendido, no un subconjunto.

* Es decir: la lista de ventanas que alimenta la bajada de ticks tiene que incluir TODOS los días marcados por E0, no sólo los E1/E4/E7/etc.

Si esos 3 puntos se cumplen, entonces sí:

💡 Puedes quedarte con UN SOLO PIPELINE (C_v2_extendido) y jubilar C_v1 como proceso operativo separado.

Esto tiene ventajas brutales:

* Un catálogo único de eventos con tipos [E0, E1, E4, E7, E8, E13…].
* Descarga de ticks unificada.
* Luego las DIBs, triple barrier, sample weights y dataset ML se construyen sobre un solo conjunto homogéneo.
* Cada fila del dataset tiene campo `event_type`. Eso es oro para ML porque ahora el modelo puede aprender “E7 (first red day) suele ser short mean-revert”, “E4 (parabolic) suele ser continuation early + fade late”, etc. Y también aprende qué hacer con E0 (que es tu catch-all info-rich).

──────────────────
4. Dónde aún hay riesgo (importante)
──────────────────

Te marco los puntos donde todavía te puedes pegar un tiro sin querer:

Riesgo A. ¿Seguro que E0 calcula RVOL igual que C_v1?
En tus versiones anteriores, RVOL lo calculabas sobre volumen regular hours o sobre total intradía (premarket+RTH+afterhours)? Y la media de 30 días incluía días sin volumen (0) o los saltabas?
→ Si esto cambia, E0 puede no marcar algunos días que C_v1 sí marcó en 2020-2025.
Solución: copiar exactamente el cálculo que usaste en build_dynamic_universe_optimized.py (el bueno que ya corriste, el que generó las watchlists y dio los 1.906 tickers info-rich).

Riesgo B. El filtro de precio ($0.50 - $20)
Ese límite lo aplicabas en C_v1 para evitar penny basura ilíquida y midcaps caros. Si en C_v2_ext para E0 no lo aplicas exactamente igual, entonces cambias el conjunto. Eso rompería la garantía de inclusión. Déjalo idéntico.

Riesgo C. Ventana temporal para descarga de ticks
En C_v1 descargabas SIEMPRE el día completo (04:00→20:00).
En C_v2 original había eventos cuya ventana era más larga o más corta (por ejemplo, FRD podía querer [D-1, D, D+1, D+2]).
Esto es bueno, no malo: ahora el unified pipeline puede asociar a cada evento su ventana propia.
Pero: asegúrate de que cuando el “evento principal” NO sea E0 (por prioridad), sigas bajando al menos la ventana del evento principal (que es a veces más grande que el puro “día D”). Eso NO rompe la compatibilidad (descargas más, no menos). Eso está bien.

Riesgo D. Delisted
C_v1 operaba solo 2020-2025 y con tickers vivos (salvo algunas adquisiciones).
En C_v2_ext vas a pasar por 2004-2025, incluyendo tickers muertos, reverse splits, tickers que vivieron un pump en 2007 y desaparecieron en 2009.
Esto es correcto para investigación histórica (sin sesgo de supervivencia), pero:

* Polygon a veces no da market cap histórico para delisted
* Polygon puede no tener todos los trades pre-2010 con la misma cobertura de microcap OTC
  → ¿Qué implica? que para tickers muertos antiguos quizá detones E0 (= info-rich) pero luego no consigas ticks reales porque la API de trades falla o devuelve parcial.

Eso no invalida la estrategia conceptual, pero sí significa: el dataset 2004-2015 va a tener más “huecos físicos” (faltan trades en origen) que 2020-2025. Eso es normal.

──────────────────
5. Qué haría yo ahora mismo
──────────────────

Yo haría esto secuencialmente:

(1) Congelar la definición de E0 como contrato.

* Literalmente copia/pega la lógica de info-rich que ya usaste para generar las watchlists 2020-2025 (esa que ya auditaste y te dio 1.906 tickers y ~11k días).
* Documenta esa lógica en un .md como “Contrato_E0.md”.
* Nadie la toca sin tu aprobación.

(2) Añadir E0 al detector de eventos de C_v2.

* Eso ya lo tenéis esbozado en el script detect_events.py extendido.
* MUY IMPORTANTE: `event_type="E0"` y `event_name="Generic_Info_Rich"` deben quedar grabados en el catálogo final.

(3) Generar un catálogo de eventos para 2020-2025 SOLO con C_v2_extendido.

* Eso produce algo tipo processed/events/events_catalog_2020_2025_extended.parquet con columnas:
  ticker, date, event_type, window_start, window_end, metrics, also_detected
* En paralelo carga tu catálogo C_v1 real (el que usaste para bajar ticks de v1).
* Cruza (ticker, date).

Esperado:

* CADA (ticker, date) de C_v1 aparece en C_v2_extendido.
* Si no aparece, entonces tu implementación de E0 no es exactamente idéntica → arreglar antes de avanzar.

Este cruce es la prueba matemática de que “C_v2_ext incluye C_v1”. Si pasa, ya está: puedes jubilar C_v1.

(4) Una vez eso pase:

* Lanzas C_v2_extendido sobre TODO 2004-2025.
* Eso ya no es “v1 vs v2”, eso es TU PIPELINE ÚNICO OFICIAL.
* Descargas ticks usando UNA SOLA LISTA: la lista de ventanas que salen de ese catálogo de eventos.
* Construyes DIBs, triple barrier, sample weights, dataset ML… todo de un único camino. Sin bifurcaciones conceptuales.

(5) Guardas una sola tabla maestra de eventos.

* Esa tabla es la biblia.
* Cada fila tiene `event_type` ∈ {E0,E1,E4,E7,E8,E13,...}.
* Esa tabla es tu “mapa de momentos relevantes del mercado small-cap desde 2004”.
* Esa tabla es la que usarás tanto para backtest histórico de estrategias humanas como para entrenar ML.

Eso, sinceramente, es exactamente lo que quieres. Es clean, auditable, defendible, y científicamente serio:

* preserva el sesgo de información (E0 = actividad anómala)
* añade clases semánticas de eventos (E1,E4,E7,E8,E13)
* respeta delistados en 2004-2025
* elimina duplicidad de pipelines.

──────────────────
Respuesta directa a “¿cómo ves esta estrategia?”
──────────────────

La estrategia de crear C_v2_extendido añadiendo E0 para absorber C_v1 me parece excelente. Es la dirección correcta. Es madura. Es escalable. Es científicamente defendible (puedes explicar cada inclusión). Y es operativa (solo un pipeline de descarga y etiquetado de eventos).

Pero hay una condición crítica:

👉 SOLO es verdad que “C_v2_ext sustituye C_v1” si E0 = C_v1 EXACTO, y si luego confirmas por código que para cada (ticker, day) que C_v1 habría marcado, C_v2_ext tiene un evento (sea E0 u otro evento de más prioridad). Esa verificación hay que ejecutarla y guardarla como auditoría, tipo `AUDITORIA_INCLUSION_v1_en_v2.json`. Eso es tu seguro legal / científico / histórico.

Haz esa auditoría y, cuando pase, ya puedes olvidarte de C_v1 como pipeline separado y vivir en C_v2_extendido para siempre.
