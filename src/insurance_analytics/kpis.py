"""Executa as consultas SQL de indicadores versionadas em `sql/kpis/`."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .config import REFERENCE_DATE, SQL_DIR, Paths

KPI_DIR = SQL_DIR / "kpis"


def default_params(year: int = REFERENCE_DATE.year, ref: date = REFERENCE_DATE) -> dict[str, int]:
    """Parâmetros padrão: ano-calendário analisado e corte de 12 meses de maturação."""
    cutoff = ref - timedelta(days=365)
    return {
        "start_key": year * 10000 + 101,
        "end_key": year * 10000 + 1231,
        "cutoff_key": int(cutoff.strftime("%Y%m%d")),
        "ref_month_idx": ref.year * 12 + ref.month - 1,
    }


def read_sql_file(path: Path, con: sqlite3.Connection, params: dict | None = None) -> pd.DataFrame:
    return pd.read_sql_query(path.read_text(encoding="utf-8"), con, params=params or {})


def kpi_name(path: Path) -> str:
    """'03_sinistralidade_produto.sql' -> 'sinistralidade_produto'."""
    return path.stem.split("_", 1)[1]


def run_all(paths: Paths, params: dict | None = None) -> dict[str, pd.DataFrame]:
    params = {**default_params(), **(params or {})}
    with sqlite3.connect(paths.warehouse) as con:
        return {kpi_name(p): read_sql_file(p, con, params) for p in sorted(KPI_DIR.glob("*.sql"))}
