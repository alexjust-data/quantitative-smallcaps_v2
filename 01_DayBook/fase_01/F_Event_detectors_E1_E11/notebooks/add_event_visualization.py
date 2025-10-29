import nbformat as nbf

# Leer el notebook ejecutado
with open('validacion_exhaustiva_descarga_pilot_ultra_light_executed.ipynb', 'r', encoding='utf-8') as f:
    nb = nbf.read(f, as_version=4)

# Crear nuevas celdas para la visualización de eventos
markdown_cell = nbf.v4.new_markdown_cell("""## 11. VISUALIZACIÓN: Eventos E1-E11 y Descargas por Ticker

Análisis visual de 3 tickers ejemplares mostrando:
- Fechas con eventos E1-E11 detectados
- Archivos de ticks descargados (evento ±2 días)
- Timeline de expansión temporal""")

code_cell_1 = nbf.v4.new_code_cell("""# Seleccionar 3 tickers representativos
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime, timedelta

# Tickers a visualizar: DCTH, ASTI, SRNE
example_tickers = ['DCTH', 'ASTI', 'SRNE']

# Cargar watchlist E1-E11
df_watchlist_full = pl.read_parquet(PROJECT_ROOT / 'processed' / 'watchlist_E1_E11.parquet')

print('=' * 100)
print('EVENTOS E1-E11: 3 TICKERS EJEMPLARES')
print('=' * 100)
print()

for ticker in example_tickers:
    ticker_events = df_watchlist_full.filter(pl.col('ticker') == ticker)
    print(f'{ticker}:')
    print(f'  Total días con eventos: {len(ticker_events):,}')
    print(f'  Eventos únicos: {ticker_events.explode("events")["events"].n_unique()}')
    print(f'  Rango fechas: {ticker_events["date"].min()} → {ticker_events["date"].max()}')
    print()""")

code_cell_2 = nbf.v4.new_code_cell("""# Preparar datos para visualización
import pandas as pd

# Colores por evento
EVENT_COLORS = {
    'E1_VolExplosion': '#e74c3c',
    'E2_GapUp': '#3498db',
    'E3_PriceSpikeIntraday': '#2ecc71',
    'E4_Parabolic': '#f39c12',
    'E5_BreakoutATH': '#9b59b6',
    'E6_MultipleGreenDays': '#1abc9c',
    'E7_FirstRedDay': '#e67e22',
    'E8_GapDownViolent': '#c0392b',
    'E9_CrashIntraday': '#16a085',
    'E10_FirstGreenBounce': '#27ae60',
    'E11_VolumeBounce': '#8e44ad',
}

# Para cada ticker, preparar timeline
ticker_timelines = {}

for ticker in example_tickers:
    # Eventos del ticker
    ticker_events = df_watchlist_full.filter(pl.col('ticker') == ticker)

    # Archivos descargados del ticker
    ticker_files = df_files.filter(pl.col('ticker') == ticker)

    # Convertir a pandas para facilitar visualización
    events_df = ticker_events.to_pandas()
    files_df = ticker_files.to_pandas()

    # Convertir fechas a datetime
    if len(events_df) > 0:
        events_df['date'] = pd.to_datetime(events_df['date'])
    if len(files_df) > 0:
        files_df['date'] = pd.to_datetime(files_df['date'])

    ticker_timelines[ticker] = {
        'events': events_df,
        'files': files_df
    }

print('Datos preparados para visualización')
print(f'Tickers procesados: {len(ticker_timelines)}')""")

code_cell_3 = nbf.v4.new_code_cell("""# Visualización 1: Timeline de eventos y descargas (3 tickers)
fig, axes = plt.subplots(3, 1, figsize=(20, 14))

for idx, ticker in enumerate(example_tickers):
    ax = axes[idx]
    data = ticker_timelines[ticker]
    events_df = data['events']
    files_df = data['files']

    if len(events_df) == 0:
        ax.text(0.5, 0.5, f'{ticker}: Sin datos', ha='center', va='center', fontsize=14)
        continue

    # Limitar a primeros 50 días con eventos para visualización clara
    events_sample = events_df.head(50).copy()

    # Obtener rango de fechas
    min_date = events_sample['date'].min()
    max_date = events_sample['date'].max()

    # Para cada evento, plotear
    y_positions = {}
    current_y = 0

    for _, row in events_sample.iterrows():
        event_date = row['date']
        events_list = row['events']

        # Plotear cada evento en esta fecha
        for event in events_list:
            if event not in y_positions:
                y_positions[event] = current_y
                current_y += 1

            y_pos = y_positions[event]
            color = EVENT_COLORS.get(event, '#95a5a6')

            # Marcar evento
            ax.scatter(event_date, y_pos, s=150, c=color, marker='o',
                      edgecolors='black', linewidths=1.5, zorder=3, alpha=0.9)

            # Marcar ventana de descarga (±2 días)
            window_start = event_date - timedelta(days=2)
            window_end = event_date + timedelta(days=2)

            ax.axvspan(window_start, window_end, ymin=y_pos/len(y_positions) if len(y_positions) > 0 else 0,
                      ymax=(y_pos+0.8)/len(y_positions) if len(y_positions) > 0 else 1,
                      alpha=0.15, color=color, zorder=1)

    # Marcar archivos descargados
    if len(files_df) > 0:
        files_in_range = files_df[(files_df['date'] >= min_date) & (files_df['date'] <= max_date)]
        for file_date in files_in_range['date'].unique():
            ax.axvline(file_date, color='green', alpha=0.2, linewidth=0.5, zorder=0)

    # Configurar ejes
    if len(y_positions) > 0:
        ax.set_yticks(range(len(y_positions)))
        ax.set_yticklabels([event.replace('_', ' ') for event in y_positions.keys()], fontsize=9)
    ax.set_xlabel('Fecha', fontsize=11, fontweight='bold')
    ax.set_title(f'{ticker}: Eventos E1-E11 y Ventanas de Descarga (primeros 50 días)',
                fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')

    # Rotar labels de fecha
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

# Leyenda general
legend_elements = [
    mpatches.Patch(facecolor='green', alpha=0.2, label='Archivo descargado'),
    mpatches.Patch(facecolor='gray', alpha=0.15, label='Ventana ±2 días'),
]
fig.legend(handles=legend_elements, loc='upper right', fontsize=10)

plt.tight_layout()
plt.savefig('eventos_E1_E11_timeline_3tickers.png', dpi=300, bbox_inches='tight')
plt.show()

print('Visualización guardada: eventos_E1_E11_timeline_3tickers.png')""")

code_cell_4 = nbf.v4.new_code_cell("""# Visualización 2: Detalle de un ticker (DCTH) - primeros 15 eventos
ticker_detail = 'DCTH'
data = ticker_timelines[ticker_detail]
events_df = data['events'].head(15).copy()
files_df = data['files']

fig, ax = plt.subplots(figsize=(20, 10))

# Para cada evento
for idx, (_, row) in enumerate(events_df.iterrows()):
    event_date = row['date']
    events_list = row['events']
    event_count = len(events_list)

    # Y position
    y_base = idx * 3

    # Título del día
    ax.text(event_date, y_base + 1.5, f'{event_date.strftime("%Y-%m-%d")}\\n({event_count} eventos)',
           ha='center', va='center', fontsize=10, fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Eventos de este día
    for event_idx, event in enumerate(events_list):
        color = EVENT_COLORS.get(event, '#95a5a6')
        y_pos = y_base + 0.5 - (event_idx * 0.3)

        ax.scatter(event_date, y_pos, s=200, c=color, marker='s',
                  edgecolors='black', linewidths=2, zorder=3)
        ax.text(event_date + timedelta(days=0.3), y_pos, event.replace('_', ' '),
               fontsize=8, va='center')

    # Ventana de descarga (±2 días)
    window_dates = [event_date + timedelta(days=d) for d in range(-2, 3)]
    for wd_idx, wd in enumerate(window_dates):
        # Verificar si se descargó
        downloaded = len(files_df[files_df['date'] == wd]) > 0

        marker = 'o' if downloaded else 'x'
        color_marker = 'green' if downloaded else 'red'
        alpha = 1.0 if downloaded else 0.3

        ax.scatter(wd, y_base - 0.5, s=100, c=color_marker, marker=marker,
                  alpha=alpha, zorder=2)

        if wd_idx == 0:
            ax.text(wd, y_base - 1, 'Descargas\\n(±2d)', ha='center',
                   fontsize=7, style='italic')

# Configuración
ax.set_ylim(-2, len(events_df) * 3)
ax.set_xlabel('Fecha', fontsize=12, fontweight='bold')
ax.set_title(f'{ticker_detail}: Detalle de Eventos E1-E11 y Descargas (primeros 15 días con eventos)',
            fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.2, axis='x')
ax.set_yticks([])

# Leyenda
legend_elements = [
    mpatches.Patch(facecolor='green', label='Archivo descargado'),
    mpatches.Patch(facecolor='red', alpha=0.3, label='No descargado (fin de semana/festivo)'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=10)

plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
plt.tight_layout()
plt.savefig(f'eventos_detalle_{ticker_detail}.png', dpi=300, bbox_inches='tight')
plt.show()

print(f'Visualización guardada: eventos_detalle_{ticker_detail}.png')""")

code_cell_5 = nbf.v4.new_code_cell("""# Estadísticas de eventos por ticker
print('=' * 100)
print('RESUMEN DE EVENTOS E1-E11 POR TICKER')
print('=' * 100)
print()

for ticker in example_tickers:
    data = ticker_timelines[ticker]
    events_df = data['events']
    files_df = data['files']

    print(f'\\n{ticker}:')
    print(f'  Días con eventos: {len(events_df):,}')
    print(f'  Archivos descargados: {len(files_df):,}')
    print(f'  Factor de expansión: {len(files_df) / len(events_df):.1f}x' if len(events_df) > 0 else '  Factor: N/A')

    # Contar eventos por tipo
    if len(events_df) > 0:
        all_events = []
        for events_list in events_df['events']:
            all_events.extend(events_list)

        from collections import Counter
        event_counts = Counter(all_events)

        print(f'  Distribución de eventos:')
        for event, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True):
            print(f'    {event}: {count}')

print()
print('=' * 100)""")

# Agregar celdas al notebook (antes de la última celda de conclusiones)
nb.cells.insert(-2, markdown_cell)
nb.cells.insert(-2, code_cell_1)
nb.cells.insert(-2, code_cell_2)
nb.cells.insert(-2, code_cell_3)
nb.cells.insert(-2, code_cell_4)
nb.cells.insert(-2, code_cell_5)

# Guardar notebook actualizado
with open('validacion_exhaustiva_descarga_pilot_ultra_light_v2.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print('Notebook actualizado con visualización de eventos creado')
print('Archivo: validacion_exhaustiva_descarga_pilot_ultra_light_v2.ipynb')
