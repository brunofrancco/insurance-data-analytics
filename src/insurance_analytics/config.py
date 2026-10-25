"""Configuração central do projeto: caminhos, datas de referência e parâmetros."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = Path(__file__).resolve().parent / "sql"

# Período coberto pelos dados sintéticos e data de corte das análises.
START_DATE = date(2023, 1, 1)
REFERENCE_DATE = date(2025, 12, 31)


@dataclass(frozen=True)
class Paths:
    """Agrupa os diretórios usados pelo pipeline.

    Recebe uma raiz para que os testes possam rodar tudo num diretório temporário.
    """

    root: Path = PROJECT_ROOT
    raw: Path = field(init=False)
    quarantine: Path = field(init=False)
    warehouse: Path = field(init=False)
    reports: Path = field(init=False)
    figures: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", self.root / "data" / "raw")
        object.__setattr__(self, "quarantine", self.root / "data" / "quarantine")
        object.__setattr__(self, "warehouse", self.root / "data" / "warehouse.db")
        object.__setattr__(self, "reports", self.root / "reports")
        object.__setattr__(self, "figures", self.root / "reports" / "figures")

    def ensure(self) -> "Paths":
        for p in (self.raw, self.quarantine, self.reports, self.figures):
            p.mkdir(parents=True, exist_ok=True)
        return self
