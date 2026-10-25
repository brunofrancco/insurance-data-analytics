"""Gráficos estáticos (matplotlib) usados no relatório e no README."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Paleta categórica validada para daltonismo (ordem fixa; a cor acompanha a entidade).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
PRODUCT_ORDER = ["Auto", "Vida", "Pet", "Celular", "Residencial", "Viagem"]
PRODUCT_COLORS = dict(zip(PRODUCT_ORDER, SERIES))
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK_MUTED, "xtick.color": INK_MUTED, "ytick.color": INK_MUTED,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
        "axes.titlecolor": INK, "font.size": 10, "legend.frameon": False, "axes.axisbelow": True,
    })


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def brl(x: float, _=None) -> str:
    if abs(x) >= 1e6:
        return f"R$ {x / 1e6:.1f} mi".replace(".", ",")
    if abs(x) >= 1e3:
        return f"R$ {x / 1e3:.0f} mil"
    return f"R$ {x:.0f}"


def premium_monthly(df: pd.DataFrame, out: Path) -> Path:
    _style()
    pivot = df.pivot(index="mes", columns="produto", values="premio_ganho")[PRODUCT_ORDER]
    x = pd.to_datetime(pivot.index)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for prod in PRODUCT_ORDER:
        ax.plot(x, pivot[prod], color=PRODUCT_COLORS[prod], lw=2, label=prod)
    # Rótulos diretos no fim das linhas, afastados para não se sobreporem.
    ends = pivot.iloc[-1].sort_values()
    min_gap = pivot.to_numpy().max() * 0.045
    ys = list(ends.to_numpy())
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + min_gap)
    for prod, y in zip(ends.index, ys):
        ax.annotate(prod, (x[-1], y), xytext=(6, 0), textcoords="offset points", va="center", color=INK_MUTED, fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(brl))
    ax.set_title("Prêmio ganho mensal por produto")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=6, loc="upper left", fontsize=9)
    ax.set_xlim(x[0], x[-1] + pd.Timedelta(days=75))
    return _save(fig, out)


def loss_ratio(df: pd.DataFrame, out: Path) -> Path:
    _style()
    d = df.sort_values("sinistralidade")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(d["produto"], d["sinistralidade"], color=SERIES[0], height=0.6)
    for y, v in enumerate(d["sinistralidade"]):
        ax.text(v + 0.01, y, f"{v:.0%}", va="center", color=INK, fontsize=9)
    ax.axvline(0.6, color=INK_MUTED, lw=1, ls="--")
    ax.text(0.605, -0.45, "referência 60%", color=INK_MUTED, fontsize=8, va="bottom")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set_xlim(0, max(0.9, d["sinistralidade"].max() + 0.1))
    ax.grid(axis="y", visible=False)
    ax.set_title("Sinistralidade por produto (sinistro incorrido / prêmio ganho)")
    return _save(fig, out)


def funnel(df: pd.DataFrame, out: Path) -> Path:
    _style()
    steps = ["ofertas_visualizadas", "simulacoes", "propostas", "contratacoes"]
    labels = ["Oferta visualizada", "Simulação", "Proposta", "Contratação"]
    totals = df[steps].sum().to_numpy()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(steps))[::-1]
    ax.barh(y, totals, color=SERIES[0], height=0.6)
    for i, (yi, v) in enumerate(zip(y, totals)):
        note = f"  ({v / totals[i - 1]:.0%} da etapa anterior)" if i else ""
        ax.text(v, yi, f"  {v:,.0f}".replace(",", ".") + note, va="center", color=INK, fontsize=9)
    ax.set_yticks(y, labels)
    ax.set_xlim(0, totals[0] * 1.55)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v / 1000:.0f} mil"))
    ax.grid(axis="y", visible=False)
    ax.set_title("Funil da jornada digital (sessões por etapa)")
    return _save(fig, out)


def cohort_heatmap(df: pd.DataFrame, out: Path) -> Path:
    _style()
    pivot = df.pivot(index="coorte", columns="meses_desde_inicio", values="retencao")
    fig, ax = plt.subplots(figsize=(8, 4.6))
    im = ax.imshow(pivot.to_numpy(), cmap="Blues", vmin=0.4, vmax=1.0, aspect="auto")
    for (i, j), v in np.ndenumerate(pivot.to_numpy()):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=8, color="white" if v > 0.75 else INK)
    ax.set_xticks(range(pivot.shape[1]), [f"M{c}" for c in pivot.columns])
    ax.set_yticks(range(pivot.shape[0]), pivot.index)
    ax.grid(False)
    ax.set_title("Retenção de apólices por coorte de contratação")
    fig.colorbar(im, ax=ax, format=mtick.PercentFormatter(1.0), shrink=0.8)
    return _save(fig, out)


def cancellation_by_payment(df: pd.DataFrame, out: Path) -> Path:
    _style()
    pivot = df.pivot(index="produto", columns="meio_pagamento", values="taxa_cancelamento_12m")
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
    methods = ["debito_conta", "cartao_credito", "pix"]
    names = {"debito_conta": "Débito em conta", "cartao_credito": "Cartão de crédito", "pix": "Pix"}
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = np.arange(len(pivot))
    w = 0.26
    for i, m in enumerate(methods):
        ax.bar(x + (i - 1) * (w + 0.02), pivot[m], width=w, color=SERIES[i], label=names[m])
    ax.set_xticks(x, pivot.index)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", ncol=3)
    ax.set_title("Cancelamento em 12 meses por produto e meio de pagamento")
    return _save(fig, out)


def roc_curves(curves: dict[str, tuple[np.ndarray, np.ndarray, float]], out: Path) -> Path:
    _style()
    fig, ax = plt.subplots(figsize=(5.5, 5))
    for i, (name, (fpr, tpr, auc)) in enumerate(curves.items()):
        ax.plot(fpr, tpr, color=SERIES[i], lw=2, label=f"{name} (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], color=INK_MUTED, lw=1, ls="--", label="Aleatório")
    ax.set_xlabel("Taxa de falsos positivos")
    ax.set_ylabel("Taxa de verdadeiros positivos")
    ax.legend(loc="lower right")
    ax.set_title("Curva ROC — base de teste")
    return _save(fig, out)


def lift_by_decile(lift: pd.DataFrame, base_rate: float, out: Path) -> Path:
    _style()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(np.arange(len(lift)), lift["taxa_cancelamento"], color=SERIES[0], width=0.65)
    ax.set_xticks(np.arange(len(lift)), lift["decil"].astype(str))
    ax.axhline(base_rate, color=INK_MUTED, ls="--", lw=1)
    ax.text(len(lift) - 0.5, base_rate, f"média {base_rate:.0%}", ha="right", va="bottom", color=INK_MUTED, fontsize=9)
    for i, v in enumerate(lift["taxa_cancelamento"]):
        ax.text(i, v + 0.005, f"{v:.0%}", ha="center", color=INK, fontsize=8)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Decil de risco previsto (1 = maior risco)")
    ax.grid(axis="x", visible=False)
    ax.set_title("Taxa real de cancelamento por decil de score")
    return _save(fig, out)
