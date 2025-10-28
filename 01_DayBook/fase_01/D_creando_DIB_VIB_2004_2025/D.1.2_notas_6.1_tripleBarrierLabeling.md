**López de Prado** explica en los capítulos 2–3 (confirmado en tus documentos) y lo que tu propio **Playbook Small Caps** adapta de manera operativa.


### De dónde salen los parámetros (base teórica)

Los valores como `pt-mul=3.0`, `sl-mul=2.0`, `t1-bars=120`, etc., **no se derivan de cuánto puede ganar una acción**, sino de **cuánto se mueve típicamente antes de invalidar o confirmar una tesis operativa** *en unidades de volatilidad σ*.

#### 1. En el método Triple Barrier

López de Prado define los límites **en múltiplos de la volatilidad local σ**, no en porcentaje fijo.
Esto convierte el sistema en **auto-escalable**:

* Si una acción se mueve un 100 %, su σ es enorme, y 3×σ cubrirá ese rango.
* Si otra se mueve solo 2 %, 3×σ será más pequeño.

👉 Es decir, `3σ` en un *runner* de +80 % puede equivaler perfectamente a un +40 % de movimiento real.

---

### ⚙️ Cómo se calibró en tu caso (basado en los dos documentos)

| Fuente                           | Recomendación original                                                                  |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| **López de Prado, 2018**         | Profit = +3σ ; Stop = −2σ ; Horizonte ≈ 2 días (p. 46)                                  |
| **Tu Playbook Small Caps (§7b)** | “Triple Barrier asimétrico: profit = 3σ, stop = 2σ, tiempo = 2 días → pumps explosivos” |

Por tanto, los parámetros que usaste **no vienen de un límite fijo en %**, sino de esta adaptación académica-operativa.

---

### Qué representan realmente

| Parámetro                          | Traducción práctica                                         | Por qué se usa                                  |
| ---------------------------------- | ----------------------------------------------------------- | ----------------------------------------------- |
| `pt-mul = 3.0`                     | Objetivo ≈ 3 × volatilidad actual                           | Distinguir “pump real” de simple rebote         |
| `sl-mul = 2.0`                     | Stop ≈ 2 × volatilidad actual                               | Stop más cercano → asimetría favor momentum     |
| `t1-bars = 120`                    | Límite temporal ≈ ½ sesión (2–3 h)                          | Define trade intradía rápido                    |
| `vol-est = ema`, `vol-window = 50` | σ calculada por EMA de retornos absolutos últimas 50 barras | Captura volatilidad actual de esa fase del pump |

---

### Si el trade sube +100 %

No pasa nada: como el umbral se mide en σ, el labeling **automáticamente** etiquetará ese movimiento como +1 mucho antes (porque habrá tocado la barrera +3σ en cuestión de minutos).
El objetivo no es capturar todo el 100 %, sino **definir el punto estadístico en que el movimiento fue significativo y validó la señal**.

---

### Si quisieras reflejar movimientos mayores (ej. 15–100 %)

Podrías:

1. **Aumentar `pt-mul` a 4 o 5** → exigir breakout aún más fuerte.
2. **Ampliar `t1-bars` a 300** → dejar respirar un swing intradía largo.
3. **Mantener `ema` adaptativa** para que σ siga escalando con la locura del día.

Pero 3σ/2σ es el *estándar académico* comprobado y el mismo que tu Playbook adoptó para calibrar el modelo sobre micro-estructura, no sobre magnitud bruta.

---

**En resumen:**
Los parámetros no salen de un % fijo de ganancia, sino de la *escala estadística de la volatilidad local* (σ).
En small caps, eso puede equivaler perfectamente a ±20–80 % reales, dependiendo de la violencia del movimiento.
Tu configuración (3σ/2σ/120 barras) es la misma que recomienda López de Prado + EduTrades y sirve como baseline sólida para etiquetar correctamente las fases explosivas sin sobre-ajustar al % nominal del pump.
