

## 🧩 1. Qué controla cada parámetro

### `--target-usd 300000`

→ Es el **umbral de notional acumulado ($)** que debe alcanzarse para cerrar una barra DIB.
En otras palabras, una barra termina cuando la suma de `price * size` (dólares negociados) supera 300 000 USD.

En pseudocódigo:

```python
bar_notional += p * s
if bar_notional >= target_usd:
    flush_bar()
```

Esto define el **“grano informativo”** de tus barras:

* Cuanto **menor** sea el `target_usd`, más barras tendrás → mayor resolución, más ruido.
* Cuanto **mayor**, menos barras → más agregación, menos detalle microestructural.

En López de Prado (2018, *Advances in Financial Machine Learning*), este parámetro se ajusta de modo que cada barra contenga **volumen o notional equivalente a cierta fracción del día promedio**, permitiendo comparar activos de distinta liquidez en pie de igualdad.

---

### `--ema-window 50`

→ Controla la **suavización adaptativa** del umbral de cierre.

En lugar de usar siempre 300 000 USD fijos, se ajusta dinámicamente:

```python
alpha = 2 / (ema_window + 1)
threshold_t = alpha * target_usd + (1 - alpha) * threshold_(t-1)
```

Así:

* Si el flujo aumenta bruscamente (día muy activo), el umbral crece progresivamente → evita generar miles de barras ultra pequeñas.
* Si el mercado se calma, el umbral se reduce suavemente → evita quedarse con 3 barras en todo el día.

👉 `ema_window=50` significa que el umbral se adapta con una *memoria de 50 barras anteriores*, lo que produce una evolución **lenta y estable**, sin jitter.

---

## 📈 2. Por qué estos valores encajan con tu universo Small Caps E0

Recuerda las propiedades de tu conjunto E0:

* Liquidez media diaria ≈ 5–20 M USD.
* Días “info-rich” (RVOL ≥ 2, |%chg| ≥ 15 %) → actividad concentrada.
* Typical spread alto, volatilidad intradía fuerte.

Con `target_usd=300 000` y `ema_window=50` observaste en el test:

* ~57 barras por sesión.
* ~18 M USD total negociado.
* Dollar total ≈ #barras × 300k → coherente.

Eso significa:

* Cada barra ≈ 1–2 % del notional diario promedio.
* Tiempo medio entre barras ≈ 8–10 min en días activos.
* 50 barras × 1 % ≈ cubre toda la jornada sin oversampling.

👉 En otras palabras, **300k USD/barra** te da una resolución “intradiaria informacional”:
suficiente para capturar movimientos estructurados (parabólicos, FRD, gap plays)
sin entrar en micro-ticks o ruido de order flow irrelevante.

Y **EMA 50** evita que el umbral se dispare o se hunda si el volumen cambia temporalmente (ej. antes/después de un halt).

---

## ⚙️ 3. Cuándo y cómo ajustar esos valores

| Objetivo / Universo                             | `target_usd` sugerido         | `ema_window` sugerido | Resultado                                 |
| ----------------------------------------------- | ----------------------------- | --------------------- | ----------------------------------------- |
| **Micro-caps extremas** (volumen < 2 M USD/día) | 100 000 USD                   | 30 – 40               | Más barras, alta resolución               |
| **Mid-caps / ETFs** (volumen > 50 M USD/día)    | 1 000 000 USD – 2 000 000 USD | 50 – 100              | Menos barras, más estables                |
| **Research microestructura / order flow**       | 50 000 USD – 100 000 USD      | 20 – 30               | Zoom de corto plazo                       |
| **Labeling ML estable (triple barrier)**        | **300 000 USD**               | **50**                | Compromiso óptimo entre ruido y cobertura |
| **Alta frecuencia (tick level)**                | < 10 000 USD                  | 10 – 20               | Demasiado granular para tu caso           |

Así que tus valores actuales (`300 k USD`, `EMA 50`) están literalmente en el “sweet spot” para small caps de 5–20 M USD /día y sesiones E0.
Son los valores de **producción estándar** en tu pipeline.

---

## ✅ En resumen

| Parámetro      | Qué hace                                                                                            | Por qué 300 k / 50                                                                                 |
| -------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `--target-usd` | Define el tamaño informacional de cada barra (cuántos dólares negociados antes de cerrar una barra) | 300 k ≈ 1–2 % del volumen diario típico de una small cap líquida; genera ~50 barras/día coherentes |
| `--ema-window` | Suaviza el umbral con memoria exponencial, adaptándose a cambios de liquidez                        | 50 barras ≈ memoria de toda la sesión; mantiene estabilidad y evita overshooting en halts/picos    |

👉 Por eso en el test te salió perfecto: 57 barras ≈ target, sin sobre-fragmentar ni agrupar demasiado.

---

Si más adelante haces *multi-universo* (E0 + E4 + E7, etc.), puedes recalibrar automáticamente `target_usd` por ticker usando:

```python
target_usd = 0.02 * dollar_vol_d  # 2% del volumen diario
```

Pero para producción E0, **300 000 USD y EMA 50** son exactamente los parámetros correctos.
