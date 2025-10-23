#!/usr/bin/env python3
"""
Script para verificar barras DIB en TradingView

Uso:
    python verify_bar_tradingview.py WOLF 2025-05-13 0
    python verify_bar_tradingview.py WOLF 2025-05-13 --largest-imbalance
    python verify_bar_tradingview.py WOLF 2025-05-13 --top-label
    python verify_bar_tradingview.py WOLF 2025-05-13 --anomaly

Argumentos:
    ticker: Símbolo a verificar (ej: WOLF, SINT, SGD)
    date: Fecha YYYY-MM-DD
    bar_index: Índice de la barra (0 = primera del día), o flags especiales:
        --largest-imbalance: Barra con mayor imbalance del día
        --top-label: Label con mayor retorno absoluto
        --anomaly: Barras con rango > 5%
        --all-stats: Mostrar estadísticas completas del día
"""

import sys
import argparse
import polars as pl
from datetime import datetime
import pytz
from pathlib import Path

# Root del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent


def utc_to_et(utc_timestamp_us):
    """Convierte timestamp UTC (μs) a ET para TradingView"""
    dt = datetime.fromtimestamp(utc_timestamp_us / 1_000_000, tz=pytz.UTC)
    et = dt.astimezone(pytz.timezone('US/Eastern'))
    return et


def verify_bar_in_tradingview(ticker, date, bar_index=0):
    """
    Genera instrucciones para verificar una barra DIB en TradingView

    Args:
        ticker: símbolo (ej: "WOLF")
        date: fecha YYYY-MM-DD (ej: "2025-05-13")
        bar_index: índice de la barra a verificar (0 = primera del día)
    """
    # Leer barra
    bars_path = PROJECT_ROOT / f"processed/bars/{ticker}/date={date}/dollar_imbalance.parquet"

    if not bars_path.exists():
        print(f"❌ No se encontró el archivo: {bars_path}")
        print(f"   Verifica que el ticker y fecha sean correctos")
        return False

    bars = pl.read_parquet(bars_path)

    if len(bars) <= bar_index:
        print(f"❌ Solo hay {len(bars)} barras ese día (pediste índice {bar_index})")
        return False

    bar = bars[bar_index]

    # Convertir timestamps
    t_open = utc_to_et(bar['t_open'][0])
    t_close = utc_to_et(bar['t_close'][0])

    # Calcular volumen total
    vol_buy = bar['cum_volume_buy'][0]
    vol_sell = bar['cum_volume_sell'][0]
    vol_total = vol_buy + vol_sell

    # Calcular dollar imbalance
    dol_buy = bar['cum_dollar_buy'][0]
    dol_sell = bar['cum_dollar_sell'][0]
    theta = bar['cum_theta'][0]

    print(f"\n{'='*70}")
    print(f"📊 VERIFICACIÓN TRADINGVIEW: {ticker} - Barra #{bar_index}")
    print(f"{'='*70}\n")

    print(f"📅 Fecha: {date}")
    print(f"⏰ Ventana temporal (ET):")
    print(f"   Open:  {t_open.strftime('%H:%M:%S.%f')[:-3]} ET")
    print(f"   Close: {t_close.strftime('%H:%M:%S.%f')[:-3]} ET")
    print(f"   Duración: {(t_close - t_open).total_seconds():.1f} segundos\n")

    print(f"💰 OHLC:")
    print(f"   Open:  ${bar['open'][0]:.2f}")
    print(f"   High:  ${bar['high'][0]:.2f}")
    print(f"   Low:   ${bar['low'][0]:.2f}")
    print(f"   Close: ${bar['close'][0]:.2f}")
    range_pct = (bar['high'][0] - bar['low'][0]) / bar['open'][0] * 100
    print(f"   Range: ${bar['high'][0] - bar['low'][0]:.2f} ({range_pct:.2f}%)\n")

    print(f"📈 Volumen:")
    print(f"   Buy:   {vol_buy:,} shares (${dol_buy:,.2f})")
    print(f"   Sell:  {vol_sell:,} shares (${dol_sell:,.2f})")
    print(f"   Total: {vol_total:,} shares\n")

    print(f"🎯 Dollar Imbalance:")
    print(f"   Theta (Σ sign): {theta:,.0f}")
    print(f"   Target: $300,000")
    print(f"   Actual: ${abs(dol_buy - dol_sell):,.2f}")
    print(f"   Buy/Sell ratio: {dol_buy/dol_sell:.2f}\n")

    print(f"{'='*70}")
    print(f"CÓMO VERIFICAR EN TRADINGVIEW:")
    print(f"{'='*70}\n")

    print(f"1. Abre TradingView → {ticker}")
    print(f"2. Timeframe: 1 minuto (o tick chart si tienes premium)")
    print(f"3. Navega a: {t_open.strftime('%b %d, %Y')}")
    print(f"4. Zoom a la ventana: {t_open.strftime('%H:%M')} - {t_close.strftime('%H:%M')} ET\n")

    print(f"5. VERIFICA:")
    print(f"   ✓ Primer precio ~${bar['open'][0]:.2f} en {t_open.strftime('%H:%M:%S')}")
    print(f"   ✓ Máximo llegó a ~${bar['high'][0]:.2f}")
    print(f"   ✓ Mínimo tocó ~${bar['low'][0]:.2f}")
    print(f"   ✓ Último precio ~${bar['close'][0]:.2f} en {t_close.strftime('%H:%M:%S')}")
    print(f"   ✓ Volumen acumulado entre {t_open.strftime('%H:%M')} - {t_close.strftime('%H:%M')}")
    print(f"     debe ser ~{vol_total:,} shares (±5% tolerancia)\n")

    # Si hay label, mostrarla también
    try:
        labels_path = PROJECT_ROOT / f"processed/labels/{ticker}/date={date}/labels.parquet"

        if labels_path.exists():
            labels = pl.read_parquet(labels_path)

            # Buscar label que coincida con t_close de esta barra
            matching = labels.filter(pl.col('anchor_ts') == bar['t_close'][0])

            if len(matching) > 0:
                lbl = matching[0]
                t1 = utc_to_et(lbl['t1'][0])

                print(f"🏷️  LABEL ASOCIADA:")
                label_str = 'WIN' if lbl['label'][0] == 1 else 'LOSS' if lbl['label'][0] == -1 else 'TIMEOUT'
                print(f"   Label: {lbl['label'][0]} ({label_str})")
                print(f"   Return: {lbl['ret'][0]:.2%}")
                print(f"   PT: {lbl['pt'][0]:.2%} (profit target)")
                print(f"   SL: {lbl['sl'][0]:.2%} (stop loss)")
                print(f"   T1: {t1.strftime('%H:%M:%S')} ET (expiry)\n")

                if lbl['label'][0] == 1:
                    print(f"   → Verifica que precio subió {lbl['ret'][0]:.2%} antes de {t1.strftime('%H:%M')}")
                elif lbl['label'][0] == -1:
                    print(f"   → Verifica que precio bajó {abs(lbl['ret'][0]):.2%} antes de {t1.strftime('%H:%M')}")
                else:
                    print(f"   → Precio no alcanzó barreras, expiró en timeout")
    except Exception as e:
        pass

    print(f"\n{'='*70}\n")
    return True


def find_largest_imbalance(ticker, date):
    """Encuentra la barra con mayor imbalance del día"""
    bars_path = PROJECT_ROOT / f"processed/bars/{ticker}/date={date}/dollar_imbalance.parquet"
    bars = pl.read_parquet(bars_path)
    bars = bars.with_columns(
        (pl.col('cum_dollar_buy') - pl.col('cum_dollar_sell')).abs().alias('imbalance')
    )
    max_idx = bars['imbalance'].arg_max()
    return max_idx


def find_top_label(ticker, date):
    """Encuentra la label con mayor retorno absoluto"""
    labels_path = PROJECT_ROOT / f"processed/labels/{ticker}/date={date}/labels.parquet"

    if not labels_path.exists():
        print(f"❌ No se encontraron labels para {ticker} en {date}")
        return None

    labels = pl.read_parquet(labels_path)
    labels = labels.with_columns(pl.col('ret').abs().alias('abs_ret'))
    top_label = labels.sort('abs_ret', descending=True).head(1)

    # Encontrar la barra que generó esa label
    bars_path = PROJECT_ROOT / f"processed/bars/{ticker}/date={date}/dollar_imbalance.parquet"
    bars = pl.read_parquet(bars_path)
    bar_match = bars.with_row_count('idx').filter(
        pl.col('t_close') == top_label['anchor_ts'][0]
    )

    if len(bar_match) == 0:
        print(f"⚠️  No se encontró la barra correspondiente a la label")
        return None

    return bar_match['idx'][0]


def find_anomalies(ticker, date):
    """Encuentra barras con rango > 5%"""
    bars_path = PROJECT_ROOT / f"processed/bars/{ticker}/date={date}/dollar_imbalance.parquet"
    bars = pl.read_parquet(bars_path)
    bars = bars.with_columns(
        ((pl.col('high') - pl.col('low')) / pl.col('open')).alias('range_pct')
    )
    anomalies = bars.filter(pl.col('range_pct') > 0.05)

    if len(anomalies) == 0:
        print(f"✅ No se encontraron anomalías (rango > 5%) en {ticker} el {date}")
        return None

    print(f"\n🔍 Encontradas {len(anomalies)} barras con rango > 5%:\n")
    return anomalies.with_row_count('idx')['idx'].to_list()


def show_day_stats(ticker, date):
    """Muestra estadísticas completas del día"""
    bars_path = PROJECT_ROOT / f"processed/bars/{ticker}/date={date}/dollar_imbalance.parquet"
    labels_path = PROJECT_ROOT / f"processed/labels/{ticker}/date={date}/labels.parquet"

    if not bars_path.exists():
        print(f"❌ No se encontraron barras para {ticker} en {date}")
        return

    bars = pl.read_parquet(bars_path)

    # Métricas de barras
    bars_with_metrics = bars.with_columns([
        ((pl.col('cum_dollar_buy') - pl.col('cum_dollar_sell')).abs().alias('imbalance')),
        ((pl.col('high') - pl.col('low')) / pl.col('open')).alias('range_pct'),
        (pl.col('cum_volume_buy') + pl.col('cum_volume_sell')).alias('total_volume')
    ])

    print(f"\n{'='*70}")
    print(f"📊 ESTADÍSTICAS DEL DÍA: {ticker} - {date}")
    print(f"{'='*70}\n")

    print(f"📈 Resumen de Barras:")
    print(f"   Total barras: {len(bars)}")
    print(f"   Imbalance promedio: ${bars_with_metrics['imbalance'].mean():,.2f}")
    print(f"   Imbalance máximo: ${bars_with_metrics['imbalance'].max():,.2f}")
    print(f"   Rango promedio: {bars_with_metrics['range_pct'].mean():.2%}")
    print(f"   Rango máximo: {bars_with_metrics['range_pct'].max():.2%}")
    print(f"   Volumen total día: {bars_with_metrics['total_volume'].sum():,} shares\n")

    # Top 5 barras por imbalance
    print(f"🎯 Top 5 Barras por Imbalance:")
    top5_imbalance = bars_with_metrics.with_row_count('idx').sort('imbalance', descending=True).head(5)
    for row in top5_imbalance.iter_rows(named=True):
        t_open = utc_to_et(row['t_open'])
        print(f"   #{row['idx']:3d} | {t_open.strftime('%H:%M:%S')} | ${row['imbalance']:>10,.2f} | Range: {row['range_pct']:>6.2%}")

    # Top 5 barras por rango
    print(f"\n📏 Top 5 Barras por Rango (volatilidad):")
    top5_range = bars_with_metrics.with_row_count('idx').sort('range_pct', descending=True).head(5)
    for row in top5_range.iter_rows(named=True):
        t_open = utc_to_et(row['t_open'])
        print(f"   #{row['idx']:3d} | {t_open.strftime('%H:%M:%S')} | ${row['open']:.2f}→${row['high']:.2f}→${row['low']:.2f} | {row['range_pct']:>6.2%}")

    # Estadísticas de labels
    if labels_path.exists():
        labels = pl.read_parquet(labels_path)

        print(f"\n🏷️  Resumen de Labels:")
        print(f"   Total labels: {len(labels)}")

        label_counts = labels.group_by('label').agg(pl.count()).sort('label')
        for row in label_counts.iter_rows(named=True):
            label_str = 'WIN' if row['label'] == 1 else 'LOSS' if row['label'] == -1 else 'TIMEOUT'
            pct = row['count'] / len(labels) * 100
            print(f"   {label_str:8s}: {row['count']:5,} ({pct:5.1f}%)")

        print(f"\n   Return promedio: {labels['ret'].mean():.2%}")
        print(f"   Return máximo: {labels['ret'].max():.2%}")
        print(f"   Return mínimo: {labels['ret'].min():.2%}")

        # Top 5 labels por retorno absoluto
        print(f"\n🏆 Top 5 Labels por Retorno Absoluto:")
        labels_with_abs = labels.with_columns(pl.col('ret').abs().alias('abs_ret'))
        top5_labels = labels_with_abs.sort('abs_ret', descending=True).head(5)

        for row in top5_labels.iter_rows(named=True):
            t0 = utc_to_et(row['anchor_ts'])
            label_str = 'WIN' if row['label'] == 1 else 'LOSS' if row['label'] == -1 else 'TIMEOUT'
            print(f"   {t0.strftime('%H:%M:%S')} | {label_str:8s} | {row['ret']:>7.2%}")

    print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Verificar barras DIB en TradingView',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Verificar primera barra del día
  python verify_bar_tradingview.py WOLF 2025-05-13 0

  # Verificar barra #10
  python verify_bar_tradingview.py WOLF 2025-05-13 10

  # Barra con mayor imbalance
  python verify_bar_tradingview.py WOLF 2025-05-13 --largest-imbalance

  # Label con mayor retorno
  python verify_bar_tradingview.py WOLF 2025-05-13 --top-label

  # Encontrar anomalías (rango > 5%)
  python verify_bar_tradingview.py WOLF 2025-05-13 --anomaly

  # Estadísticas completas del día
  python verify_bar_tradingview.py WOLF 2025-05-13 --all-stats
        """
    )

    parser.add_argument('ticker', help='Símbolo del ticker (ej: WOLF)')
    parser.add_argument('date', help='Fecha YYYY-MM-DD')
    parser.add_argument('bar_index', nargs='?', default='0',
                       help='Índice de la barra (default: 0)')
    parser.add_argument('--largest-imbalance', action='store_true',
                       help='Mostrar barra con mayor imbalance')
    parser.add_argument('--top-label', action='store_true',
                       help='Mostrar label con mayor retorno')
    parser.add_argument('--anomaly', action='store_true',
                       help='Mostrar barras con rango > 5%%')
    parser.add_argument('--all-stats', action='store_true',
                       help='Mostrar estadísticas completas del día')

    args = parser.parse_args()

    ticker = args.ticker.upper()
    date = args.date

    try:
        if args.all_stats:
            show_day_stats(ticker, date)
            return

        if args.largest_imbalance:
            idx = find_largest_imbalance(ticker, date)
            print(f"\n🎯 Barra con MAYOR IMBALANCE del día: índice {idx}\n")
            verify_bar_in_tradingview(ticker, date, idx)

        elif args.top_label:
            idx = find_top_label(ticker, date)
            if idx is not None:
                print(f"\n🏆 Barra con MAYOR RETORNO (label) del día: índice {idx}\n")
                verify_bar_in_tradingview(ticker, date, idx)

        elif args.anomaly:
            indices = find_anomalies(ticker, date)
            if indices:
                for i, idx in enumerate(indices, 1):
                    print(f"\n{'#'*70}")
                    print(f"ANOMALÍA {i}/{len(indices)}")
                    print(f"{'#'*70}")
                    verify_bar_in_tradingview(ticker, date, idx)

        else:
            bar_index = int(args.bar_index)
            verify_bar_in_tradingview(ticker, date, bar_index)

    except FileNotFoundError as e:
        print(f"\n❌ Error: No se encontraron datos para {ticker} en {date}")
        print(f"   Verifica que el ticker y fecha existan en processed/bars/")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
