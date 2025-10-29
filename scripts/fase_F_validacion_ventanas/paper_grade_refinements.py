#!/usr/bin/env python
"""
paper_grade_refinements.py
Refinamientos "paper-grade" para validación híbrida de ventanas:
1. Normalized Mutual Information (NMI)
2. Heatmap bidimensional (evento × t)
3. Coeficiente de concordancia Spearman
4. Score híbrido automático
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr, entropy
from sklearn.metrics import mutual_info_score, normalized_mutual_info_score
from typing import Dict, Tuple


def calculate_normalized_mutual_information(
    X: np.ndarray,
    y: np.ndarray,
    bins: int = 10,
    average_method: str = 'arithmetic'
) -> float:
    """
    Calcula Normalized Mutual Information (NMI) entre features X y target y.

    NMI(X;y) = MI(X;y) / [average(H(X), H(y))]

    Donde average puede ser:
    - 'arithmetic': (H(X) + H(y)) / 2
    - 'geometric': sqrt(H(X) * H(y))
    - 'max': max(H(X), H(y))
    - 'min': min(H(X), H(y))

    Args:
        X: Features (N_samples, N_features)
        y: Target (N_samples,)
        bins: Bins para discretización
        average_method: Método de promedio para normalización

    Returns:
        NMI score normalizado [0, 1]
    """
    y_binned = pd.cut(y, bins=bins, labels=False, duplicates='drop')

    nmi_scores = []
    for col_idx in range(X.shape[1]):
        x_col = X[:, col_idx]
        x_binned = pd.cut(x_col, bins=bins, labels=False, duplicates='drop')

        valid_mask = ~(pd.isna(x_binned) | pd.isna(y_binned))
        if valid_mask.sum() > 10:
            nmi = normalized_mutual_info_score(
                x_binned[valid_mask],
                y_binned[valid_mask],
                average_method=average_method
            )
            nmi_scores.append(nmi)

    return np.mean(nmi_scores) if nmi_scores else 0.0


def plot_heatmap_event_x_time(
    info_results: Dict[str, Dict[int, float]],
    edge_results: Dict[str, Dict[int, float]] = None,
    figsize: Tuple[int, int] = (14, 8)
) -> plt.Figure:
    """
    Crea heatmap bidimensional (evento × día_relativo) para MI y opcionalmente Edge.

    Args:
        info_results: {event: {rel_day: MI_score}}
        edge_results: {event: {rel_day: edge_score}} (opcional)
        figsize: Tamaño de figura

    Returns:
        Matplotlib Figure
    """
    # Construir matriz para heatmap
    events = sorted(info_results.keys())
    all_days = set()
    for event_data in info_results.values():
        all_days.update(event_data.keys())
    days = sorted(all_days)

    # Matriz MI
    mi_matrix = []
    for event in events:
        row = [info_results[event].get(d, 0.0) for d in days]
        mi_matrix.append(row)

    mi_df = pd.DataFrame(mi_matrix, index=events, columns=days)

    # Si hay edge results, crear subplot
    if edge_results is not None:
        fig, axes = plt.subplots(1, 2, figsize=(figsize[0] * 2, figsize[1]))

        # Heatmap MI
        sns.heatmap(
            mi_df,
            ax=axes[0],
            cmap='YlOrRd',
            cbar_kws={'label': 'Mutual Information (normalizado)'},
            vmin=0,
            vmax=1,
            annot=False,
            fmt='.2f'
        )
        axes[0].set_title('Información Mutua por Evento y Día Relativo', fontsize=14)
        axes[0].set_xlabel('Días Relativos al Evento')
        axes[0].set_ylabel('Evento')
        axes[0].axvline(x=days.index(0) + 0.5, color='red', linestyle='--', linewidth=2, alpha=0.7)

        # Matriz Edge
        edge_matrix = []
        for event in events:
            row = [edge_results[event].get(d, 0.0) for d in days]
            edge_matrix.append(row)

        edge_df = pd.DataFrame(edge_matrix, index=events, columns=days)

        # Heatmap Edge
        sns.heatmap(
            edge_df,
            ax=axes[1],
            cmap='RdYlGn',
            center=0,
            cbar_kws={'label': 'Edge Económico'},
            annot=False,
            fmt='.3f'
        )
        axes[1].set_title('Edge Económico por Evento y Día Relativo', fontsize=14)
        axes[1].set_xlabel('Días Relativos al Evento')
        axes[1].set_ylabel('Evento')
        axes[1].axvline(x=days.index(0) + 0.5, color='red', linestyle='--', linewidth=2, alpha=0.7)

    else:
        fig, ax = plt.subplots(figsize=figsize)
        sns.heatmap(
            mi_df,
            ax=ax,
            cmap='YlOrRd',
            cbar_kws={'label': 'Mutual Information (normalizado)'},
            vmin=0,
            vmax=1,
            annot=True,
            fmt='.2f'
        )
        ax.set_title('Información Mutua por Evento y Día Relativo', fontsize=14)
        ax.set_xlabel('Días Relativos al Evento')
        ax.set_ylabel('Evento')
        ax.axvline(x=days.index(0) + 0.5, color='red', linestyle='--', linewidth=2, alpha=0.7)

    plt.tight_layout()
    return fig


def calculate_concordance_spearman(
    mi_results: Dict[str, float],
    edge_results: Dict[str, float]
) -> Tuple[float, float]:
    """
    Calcula correlación de Spearman entre rankings de MI y Edge.

    Mide formalmente la consistencia entre ambos criterios:
    - ρ ≈ 1: Ambos criterios concuerdan (ventanas con alta MI también tienen alto edge)
    - ρ ≈ 0: No hay relación
    - ρ ≈ -1: Criterios opuestos (alta MI pero bajo edge)

    Args:
        mi_results: {window_id: MI_score}
        edge_results: {window_id: edge_score}

    Returns:
        (rho, p_value): Coeficiente Spearman y significancia estadística
    """
    # Alinear ventanas comunes
    common_keys = set(mi_results.keys()) & set(edge_results.keys())

    if len(common_keys) < 3:
        return (np.nan, np.nan)

    mi_values = [mi_results[k] for k in common_keys]
    edge_values = [edge_results[k] for k in common_keys]

    rho, p_value = spearmanr(mi_values, edge_values)

    return (rho, p_value)


def hybrid_score_selection(
    mi_scores: np.ndarray,
    edge_scores: np.ndarray,
    alpha: float = 0.6,
    quantile_threshold: float = 0.8
) -> np.ndarray:
    """
    Selección híbrida de ventanas usando score combinado.

    Score_hybrid = α * MI_norm + (1 - α) * edge_norm

    Args:
        mi_scores: Array de scores MI
        edge_scores: Array de scores edge
        alpha: Peso para MI (default 0.6 → más peso a información)
        quantile_threshold: Percentil para filtrar (default 0.8 → top 20%)

    Returns:
        Boolean mask indicando ventanas seleccionadas
    """
    # Normalizar ambos scores a [0, 1]
    mi_norm = (mi_scores - mi_scores.min()) / (mi_scores.max() - mi_scores.min() + 1e-10)
    edge_norm = (edge_scores - edge_scores.min()) / (edge_scores.max() - edge_scores.min() + 1e-10)

    # Score híbrido
    hybrid = alpha * mi_norm + (1 - alpha) * edge_norm

    # Threshold
    threshold = np.quantile(hybrid, quantile_threshold)

    return hybrid >= threshold


def plot_concordance_analysis(
    mi_results: Dict[str, float],
    edge_results: Dict[str, float],
    window_labels: Dict[str, str] = None,
    figsize: Tuple[int, int] = (12, 8)
) -> plt.Figure:
    """
    Visualiza análisis de concordancia entre MI y Edge.

    Args:
        mi_results: {window_id: MI_score}
        edge_results: {window_id: edge_score}
        window_labels: {window_id: label} para anotaciones
        figsize: Tamaño figura

    Returns:
        Matplotlib Figure
    """
    # Alinear datos
    common_keys = sorted(set(mi_results.keys()) & set(edge_results.keys()))
    mi_values = np.array([mi_results[k] for k in common_keys])
    edge_values = np.array([edge_results[k] for k in common_keys])

    # Calcular concordancia
    rho, p_value = spearmanr(mi_values, edge_values)

    fig, axes = plt.subplots(2, 2, figsize=figsize)

    # 1. Scatter MI vs Edge
    ax = axes[0, 0]
    ax.scatter(mi_values, edge_values, alpha=0.6, s=100, c=mi_values, cmap='viridis')

    # Regresión lineal para visualizar tendencia
    z = np.polyfit(mi_values, edge_values, 1)
    p = np.poly1d(z)
    ax.plot(mi_values, p(mi_values), "r--", alpha=0.8, linewidth=2)

    ax.set_xlabel('Mutual Information (normalizado)')
    ax.set_ylabel('Edge Económico')
    ax.set_title(f'Concordancia: ρ={rho:.3f}, p={p_value:.4f}')
    ax.grid(True, alpha=0.3)

    # Anotar puntos extremos
    if window_labels:
        # Top MI
        top_mi_idx = np.argmax(mi_values)
        ax.annotate(
            window_labels.get(common_keys[top_mi_idx], common_keys[top_mi_idx]),
            (mi_values[top_mi_idx], edge_values[top_mi_idx]),
            xytext=(10, 10),
            textcoords='offset points',
            fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7)
        )

        # Top Edge
        top_edge_idx = np.argmax(edge_values)
        ax.annotate(
            window_labels.get(common_keys[top_edge_idx], common_keys[top_edge_idx]),
            (mi_values[top_edge_idx], edge_values[top_edge_idx]),
            xytext=(10, -20),
            textcoords='offset points',
            fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7)
        )

    # 2. Rank-Rank Plot
    ax = axes[0, 1]
    mi_ranks = pd.Series(mi_values).rank()
    edge_ranks = pd.Series(edge_values).rank()

    ax.scatter(mi_ranks, edge_ranks, alpha=0.6, s=100)
    ax.plot([1, len(mi_values)], [1, len(mi_values)], 'k--', alpha=0.5, label='Concordancia perfecta')
    ax.set_xlabel('Rank(MI)')
    ax.set_ylabel('Rank(Edge)')
    ax.set_title('Rank-Rank Plot')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 3. Distribuciones
    ax = axes[1, 0]
    ax.hist(mi_values, bins=20, alpha=0.6, label='MI', color='blue', density=True)
    ax.hist(edge_values, bins=20, alpha=0.6, label='Edge', color='green', density=True)
    ax.set_xlabel('Score Value')
    ax.set_ylabel('Density')
    ax.set_title('Distribuciones de Scores')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # 4. Hybrid Score Distribution
    ax = axes[1, 1]
    alpha = 0.6
    mi_norm = (mi_values - mi_values.min()) / (mi_values.max() - mi_values.min() + 1e-10)
    edge_norm = (edge_values - edge_values.min()) / (edge_values.max() - edge_values.min() + 1e-10)
    hybrid = alpha * mi_norm + (1 - alpha) * edge_norm

    ax.hist(hybrid, bins=20, alpha=0.7, color='purple', edgecolor='black')
    threshold = np.quantile(hybrid, 0.8)
    ax.axvline(threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold (q=0.8): {threshold:.3f}')
    ax.set_xlabel('Hybrid Score')
    ax.set_ylabel('Frequency')
    ax.set_title(f'Hybrid Score (α={alpha})')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    return fig


def summary_statistics_report(
    mi_results: Dict[str, float],
    edge_results: Dict[str, float]
) -> pd.DataFrame:
    """
    Genera reporte estadístico completo de concordancia.

    Returns:
        DataFrame con estadísticas descriptivas y concordancia
    """
    common_keys = sorted(set(mi_results.keys()) & set(edge_results.keys()))
    mi_values = np.array([mi_results[k] for k in common_keys])
    edge_values = np.array([edge_results[k] for k in common_keys])

    rho, p_value = spearmanr(mi_values, edge_values)

    report = {
        'Metric': [
            'N Ventanas',
            'MI Mean', 'MI Std', 'MI Min', 'MI Max',
            'Edge Mean', 'Edge Std', 'Edge Min', 'Edge Max',
            'Spearman ρ', 'P-value',
            'Concordancia Interpretación'
        ],
        'Value': [
            len(common_keys),
            mi_values.mean(), mi_values.std(), mi_values.min(), mi_values.max(),
            edge_values.mean(), edge_values.std(), edge_values.min(), edge_values.max(),
            rho, p_value,
            'Alta' if rho > 0.7 else ('Moderada' if rho > 0.4 else 'Baja')
        ]
    }

    return pd.DataFrame(report)


if __name__ == "__main__":
    print("✓ Refinamientos paper-grade definidos")
    print("\nFunciones disponibles:")
    print("  1. calculate_normalized_mutual_information() - NMI normalizado")
    print("  2. plot_heatmap_event_x_time() - Heatmap 2D evento×tiempo")
    print("  3. calculate_concordance_spearman() - Correlación rankings")
    print("  4. hybrid_score_selection() - Selección híbrida automática")
    print("  5. plot_concordance_analysis() - Visualización completa concordancia")
    print("  6. summary_statistics_report() - Reporte estadístico")
