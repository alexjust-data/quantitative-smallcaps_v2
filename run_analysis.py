"""
Script para ejecutar análisis visual de estadísticas del universo
"""
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configurar estilo
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (15, 8)
plt.rcParams['font.size'] = 10

print("=" * 80)
print("ANÁLISIS VISUAL DE ESTADÍSTICAS DEL UNIVERSO")
print("=" * 80)

# Cargar datos
project_root = Path(r"D:\04_TRADING_SMALLCAPS")
stats_file = project_root / "stats_daily_cache.json"
output_dir = project_root / "01_DayBook" / "fase_01" / "A_Universo" / "graficas"
output_dir.mkdir(exist_ok=True)

print(f"\nCargando: {stats_file}")
with open(stats_file, 'r') as f:
    data = json.load(f)

tickers_data = data['tickers']
print(f"[OK] Total tickers cargados: {len(tickers_data):,}")

df = pd.DataFrame(tickers_data)
print(f"[OK] DataFrame creado con {len(df)} filas y {len(df.columns)} columnas")

# ============================================================================
# 1. ANÁLISIS TEMPORAL
# ============================================================================
print("\n" + "=" * 80)
print("1. EXTRAYENDO DATOS TEMPORALES")
print("=" * 80)

temporal_data = []
for ticker_info in tickers_data:
    if ticker_info['status'] == 'success' and 'temporal' in ticker_info:
        temporal = ticker_info['temporal']
        temporal_data.append({
            'ticker': ticker_info['ticker'],
            'min_date': temporal['min_date'],
            'max_date': temporal['max_date'],
            'total_days': temporal['total_days'],
            'years_covered': temporal['years_covered'],
            'date_range_calendar': temporal['date_range_calendar']
        })

df_temporal = pd.DataFrame(temporal_data)
df_temporal['min_date'] = pd.to_datetime(df_temporal['min_date'])
df_temporal['max_date'] = pd.to_datetime(df_temporal['max_date'])
df_temporal['min_year'] = df_temporal['min_date'].dt.year
df_temporal['max_year'] = df_temporal['max_date'].dt.year

print(f"Tickers con datos temporales: {len(df_temporal):,}")

# GRÁFICA 1: Distribución temporal
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

axes[0, 0].hist(df_temporal['years_covered'], bins=50, color='skyblue', edgecolor='black', alpha=0.7)
axes[0, 0].set_xlabel('Años de Cobertura')
axes[0, 0].set_ylabel('Número de Tickers')
axes[0, 0].set_title('Distribución de Años de Cobertura por Ticker')
axes[0, 0].axvline(df_temporal['years_covered'].median(), color='red', linestyle='--',
                   label=f'Mediana: {df_temporal["years_covered"].median():.2f} años')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].hist(df_temporal['total_days'], bins=50, color='lightcoral', edgecolor='black', alpha=0.7)
axes[0, 1].set_xlabel('Días de Trading')
axes[0, 1].set_ylabel('Número de Tickers')
axes[0, 1].set_title('Distribución de Días Totales de Trading')
axes[0, 1].axvline(df_temporal['total_days'].median(), color='red', linestyle='--',
                   label=f'Mediana: {df_temporal["total_days"].median():.0f} días')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.3)

year_start_counts = df_temporal['min_year'].value_counts().sort_index()
axes[1, 0].bar(year_start_counts.index, year_start_counts.values, color='green', alpha=0.7)
axes[1, 0].set_xlabel('Año de Inicio')
axes[1, 0].set_ylabel('Número de Tickers')
axes[1, 0].set_title('Tickers: Año de Inicio de Datos')
axes[1, 0].tick_params(axis='x', rotation=45)
axes[1, 0].grid(True, alpha=0.3)

year_end_counts = df_temporal['max_year'].value_counts().sort_index()
axes[1, 1].bar(year_end_counts.index, year_end_counts.values, color='orange', alpha=0.7)
axes[1, 1].set_xlabel('Año de Fin')
axes[1, 1].set_ylabel('Número de Tickers')
axes[1, 1].set_title('Tickers: Año de Fin de Datos')
axes[1, 1].tick_params(axis='x', rotation=45)
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / "01_analisis_temporal.png", dpi=150, bbox_inches='tight')
print(f"[OK] Gráfica guardada: 01_analisis_temporal.png")
plt.close()

print(f"\nESTADÍSTICAS TEMPORALES:")
print(f"  • Cobertura promedio: {df_temporal['years_covered'].mean():.2f} años")
print(f"  • Cobertura mediana: {df_temporal['years_covered'].median():.2f} años")
print(f"  • Días de trading promedio: {df_temporal['total_days'].mean():.0f}")
print(f"  • Año más antiguo: {df_temporal['min_year'].min()}")
print(f"  • Año más reciente: {df_temporal['max_year'].max()}")

# ============================================================================
# 2. CALIDAD DE DATOS
# ============================================================================
print("\n" + "=" * 80)
print("2. EXTRAYENDO DATOS DE CALIDAD")
print("=" * 80)

quality_data = []
for ticker_info in tickers_data:
    quality_data.append({
        'ticker': ticker_info['ticker'],
        'status': ticker_info['status'],
        'has_data': ticker_info['status'] == 'success'
    })

    if ticker_info['status'] == 'success' and 'null_counts' in ticker_info:
        nulls = ticker_info['null_counts']
        quality_data[-1]['market_cap_null_pct'] = nulls.get('market_cap_d', {}).get('percentage', 0)
        quality_data[-1]['pctchg_null_pct'] = nulls.get('pctchg_d', {}).get('percentage', 0)
        quality_data[-1]['return_null_pct'] = nulls.get('return_d', {}).get('percentage', 0)

    if ticker_info['status'] == 'success' and 'dimensions' in ticker_info:
        quality_data[-1]['total_rows'] = ticker_info['dimensions'].get('rows', 0)

df_quality = pd.DataFrame(quality_data)
print(f"Datos de calidad extraídos: {len(df_quality):,} tickers")

# GRÁFICA 2: Calidad de datos
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

status_counts = df_quality['status'].value_counts()
axes[0, 0].pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
axes[0, 0].set_title(f'Status de Tickers (Total: {len(df_quality):,})')

df_success = df_quality[df_quality['status'] == 'success'].copy()
if 'market_cap_null_pct' in df_quality.columns:
    axes[0, 1].hist(df_success['market_cap_null_pct'].dropna(), bins=50, color='purple', alpha=0.7, edgecolor='black')
    axes[0, 1].set_xlabel('% Nulls en Market Cap')
    axes[0, 1].set_ylabel('Número de Tickers')
    axes[0, 1].set_title('Distribución de Nulls en Market Cap')
    axes[0, 1].axvline(100, color='red', linestyle='--', label='100% Nulls')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

if 'total_rows' in df_quality.columns:
    axes[1, 0].hist(df_success['total_rows'].dropna(), bins=50, color='teal', alpha=0.7, edgecolor='black')
    axes[1, 0].set_xlabel('Número de Filas')
    axes[1, 0].set_ylabel('Número de Tickers')
    axes[1, 0].set_title('Distribución de Filas por Ticker')
    axes[1, 0].set_yscale('log')
    axes[1, 0].grid(True, alpha=0.3)

if 'total_rows' in df_quality.columns:
    top_20 = df_success.nlargest(20, 'total_rows')[['ticker', 'total_rows']]
    axes[1, 1].barh(range(len(top_20)), top_20['total_rows'].values, color='steelblue')
    axes[1, 1].set_yticks(range(len(top_20)))
    axes[1, 1].set_yticklabels(top_20['ticker'].values)
    axes[1, 1].set_xlabel('Número de Filas')
    axes[1, 1].set_title('Top 20 Tickers con Más Datos')
    axes[1, 1].invert_yaxis()
    axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / "02_calidad_datos.png", dpi=150, bbox_inches='tight')
print(f"[OK] Gráfica guardada: 02_calidad_datos.png")
plt.close()

print(f"\nCALIDAD DE DATOS:")
print(f"  • Tickers exitosos: {status_counts.get('success', 0):,} ({status_counts.get('success', 0)/len(df_quality)*100:.1f}%)")
if 'market_cap_null_pct' in df_quality.columns:
    tickers_sin_mcap = (df_success['market_cap_null_pct'] == 100).sum()
    print(f"  • Tickers sin market cap: {tickers_sin_mcap:,} ({tickers_sin_mcap/len(df_success)*100:.1f}%)")
if 'total_rows' in df_quality.columns:
    print(f"  • Promedio de filas por ticker: {df_success['total_rows'].mean():.0f}")

# ============================================================================
# 3. ESTADÍSTICAS DE TRADING
# ============================================================================
print("\n" + "=" * 80)
print("3. EXTRAYENDO ESTADÍSTICAS DE TRADING")
print("=" * 80)

trading_stats = []
for ticker_info in tickers_data:
    if ticker_info['status'] == 'success' and 'columns_stats' in ticker_info:
        stats = ticker_info['columns_stats']
        trading_stats.append({
            'ticker': ticker_info['ticker'],
            'close_mean': stats.get('close_d', {}).get('mean'),
            'vol_mean': stats.get('vol_d', {}).get('mean'),
            'dollar_vol_mean': stats.get('dollar_vol_d', {}).get('mean'),
            'pctchg_std': stats.get('pctchg_d', {}).get('std'),
            'rvol30_mean': stats.get('rvol30', {}).get('mean'),
            'session_rows_mean': stats.get('session_rows', {}).get('mean')
        })

df_trading = pd.DataFrame(trading_stats)
print(f"Estadísticas de trading extraídas: {len(df_trading):,} tickers")

# GRÁFICA 3: Estadísticas de Trading
fig, axes = plt.subplots(2, 3, figsize=(18, 12))

axes[0, 0].hist(df_trading['close_mean'].dropna(), bins=100, color='blue', alpha=0.7, edgecolor='black')
axes[0, 0].set_xlabel('Precio Medio ($)')
axes[0, 0].set_ylabel('Número de Tickers')
axes[0, 0].set_title('Distribución de Precios Medios')
axes[0, 0].set_xlim(0, df_trading['close_mean'].quantile(0.95))
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].hist(np.log10(df_trading['vol_mean'].dropna() + 1), bins=50, color='green', alpha=0.7, edgecolor='black')
axes[0, 1].set_xlabel('Log10(Volumen Promedio)')
axes[0, 1].set_ylabel('Número de Tickers')
axes[0, 1].set_title('Distribución de Volumen Promedio (Log Scale)')
axes[0, 1].grid(True, alpha=0.3)

axes[0, 2].hist(np.log10(df_trading['dollar_vol_mean'].dropna() + 1), bins=50, color='orange', alpha=0.7, edgecolor='black')
axes[0, 2].set_xlabel('Log10(Dollar Volume Promedio)')
axes[0, 2].set_ylabel('Número de Tickers')
axes[0, 2].set_title('Distribución de Dollar Volume (Log Scale)')
axes[0, 2].grid(True, alpha=0.3)

axes[1, 0].hist(df_trading['pctchg_std'].dropna() * 100, bins=50, color='red', alpha=0.7, edgecolor='black')
axes[1, 0].set_xlabel('Volatilidad Diaria (% std)')
axes[1, 0].set_ylabel('Número de Tickers')
axes[1, 0].set_title('Distribución de Volatilidad Diaria')
axes[1, 0].set_xlim(0, df_trading['pctchg_std'].quantile(0.95) * 100)
axes[1, 0].grid(True, alpha=0.3)

axes[1, 1].hist(df_trading['rvol30_mean'].dropna(), bins=50, color='purple', alpha=0.7, edgecolor='black')
axes[1, 1].set_xlabel('RVOL30 Promedio')
axes[1, 1].set_ylabel('Número de Tickers')
axes[1, 1].set_title('Distribución de Volumen Relativo (RVOL30)')
axes[1, 1].axvline(1.0, color='red', linestyle='--', label='RVOL = 1.0')
axes[1, 1].legend()
axes[1, 1].grid(True, alpha=0.3)

axes[1, 2].hist(df_trading['session_rows_mean'].dropna(), bins=50, color='teal', alpha=0.7, edgecolor='black')
axes[1, 2].set_xlabel('Filas Promedio por Sesión')
axes[1, 2].set_ylabel('Número de Tickers')
axes[1, 2].set_title('Distribución de Datos Intraday por Sesión')
axes[1, 2].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / "03_estadisticas_trading.png", dpi=150, bbox_inches='tight')
print(f"[OK] Gráfica guardada: 03_estadisticas_trading.png")
plt.close()

print(f"\nESTADÍSTICAS DE TRADING:")
print(f"  • Precio medio promedio: ${df_trading['close_mean'].mean():.2f}")
print(f"  • Volumen promedio: {df_trading['vol_mean'].mean():,.0f}")
print(f"  • Dollar volume promedio: ${df_trading['dollar_vol_mean'].mean():,.0f}")
print(f"  • Volatilidad promedio: {df_trading['pctchg_std'].mean()*100:.2f}%")

# ============================================================================
# 4. LIQUIDEZ Y ACTIVIDAD
# ============================================================================
print("\n" + "=" * 80)
print("4. EXTRAYENDO DATOS DE LIQUIDEZ")
print("=" * 80)

domain_data = []
for ticker_info in tickers_data:
    if ticker_info['status'] == 'success' and 'domain_stats' in ticker_info:
        domain = ticker_info['domain_stats']
        domain_data.append({
            'ticker': ticker_info['ticker'],
            'dollar_vol_gte_5M_pct': domain.get('dollar_vol_gte_5M', {}).get('percentage', 0),
            'pctchg_abs_gte_15pct_pct': domain.get('pctchg_abs_gte_15pct', {}).get('percentage', 0),
            'rvol30_gte_2_pct': domain.get('rvol30_gte_2', {}).get('percentage', 0),
            'e0_days_pct': domain.get('e0_days', {}).get('percentage', 0)
        })

df_domain = pd.DataFrame(domain_data)
print(f"Domain stats extraídas: {len(df_domain):,} tickers")

# GRÁFICA 4: Liquidez y actividad
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

axes[0, 0].hist(df_domain['dollar_vol_gte_5M_pct'].dropna(), bins=50, color='gold', alpha=0.7, edgecolor='black')
axes[0, 0].set_xlabel('% de Días con Dollar Vol >= $5M')
axes[0, 0].set_ylabel('Número de Tickers')
axes[0, 0].set_title('Liquidez: Días con Dollar Volume >= $5M')
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].hist(df_domain['pctchg_abs_gte_15pct_pct'].dropna(), bins=50, color='crimson', alpha=0.7, edgecolor='black')
axes[0, 1].set_xlabel('% de Días con |Cambio| >= 15%')
axes[0, 1].set_ylabel('Número de Tickers')
axes[0, 1].set_title('Volatilidad Extrema: Días con Cambio >= 15%')
axes[0, 1].grid(True, alpha=0.3)

axes[1, 0].hist(df_domain['rvol30_gte_2_pct'].dropna(), bins=50, color='lime', alpha=0.7, edgecolor='black')
axes[1, 0].set_xlabel('% de Días con RVOL >= 2x')
axes[1, 0].set_ylabel('Número de Tickers')
axes[1, 0].set_title('Alto Volumen: Días con RVOL >= 2x')
axes[1, 0].grid(True, alpha=0.3)

liquid_tickers = (df_domain['dollar_vol_gte_5M_pct'] > 50).sum()
low_liquid_tickers = (df_domain['dollar_vol_gte_5M_pct'] <= 10).sum()
med_liquid_tickers = len(df_domain) - liquid_tickers - low_liquid_tickers

liquidity_categories = ['Alta Liquidez\n(>50% días ≥$5M)', 'Media Liquidez', 'Baja Liquidez\n(≤10% días ≥$5M)']
liquidity_counts = [liquid_tickers, med_liquid_tickers, low_liquid_tickers]
colors = ['green', 'yellow', 'red']

axes[1, 1].bar(liquidity_categories, liquidity_counts, color=colors, alpha=0.7, edgecolor='black')
axes[1, 1].set_ylabel('Número de Tickers')
axes[1, 1].set_title('Clasificación de Tickers por Liquidez')
axes[1, 1].grid(True, alpha=0.3, axis='y')

for i, (cat, count) in enumerate(zip(liquidity_categories, liquidity_counts)):
    axes[1, 1].text(i, count, f'{count:,}\n({count/len(df_domain)*100:.1f}%)',
                    ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
plt.savefig(output_dir / "04_liquidez_actividad.png", dpi=150, bbox_inches='tight')
print(f"[OK] Gráfica guardada: 04_liquidez_actividad.png")
plt.close()

print(f"\nLIQUIDEZ Y ACTIVIDAD:")
print(f"  • Tickers con alta liquidez: {liquid_tickers:,} ({liquid_tickers/len(df_domain)*100:.1f}%)")
print(f"  • Tickers con baja liquidez: {low_liquid_tickers:,} ({low_liquid_tickers/len(df_domain)*100:.1f}%)")

# ============================================================================
# 5. RESUMEN CONSOLIDADO
# ============================================================================
print("\n" + "=" * 80)
print("5. GENERANDO RESUMEN CONSOLIDADO")
print("=" * 80)

df_summary = df_temporal.merge(df_quality[['ticker', 'status', 'market_cap_null_pct', 'total_rows']], on='ticker', how='left')
df_summary = df_summary.merge(df_trading, on='ticker', how='left')
df_summary = df_summary.merge(df_domain, on='ticker', how='left')

output_file = project_root / "analysis_summary.csv"
df_summary.to_csv(output_file, index=False)
print(f"[OK] Resumen exportado a: {output_file}")

print("\n" + "=" * 80)
print("RESUMEN EJECUTIVO")
print("=" * 80)
print(f"\nTOTAL TICKERS: {len(df):,}")
print(f"Tickers exitosos: {(df_quality['status'] == 'success').sum():,}")
print(f"\nCOBERTURA TEMPORAL:")
print(f"  • Rango: {df_temporal['min_year'].min()} - {df_temporal['max_year'].max()}")
print(f"  • Promedio: {df_temporal['years_covered'].mean():.2f} años")
print(f"\nGRÁFICAS GENERADAS:")
print(f"  • 01_analisis_temporal.png")
print(f"  • 02_calidad_datos.png")
print(f"  • 03_estadisticas_trading.png")
print(f"  • 04_liquidez_actividad.png")
print(f"\nArchivos guardados en: {output_dir}")
print("\n" + "=" * 80)
print("[OK] ANÁLISIS COMPLETADO")
print("=" * 80)
