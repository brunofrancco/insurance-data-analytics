"""Validação de qualidade de dados.

Cada regra é declarada uma única vez como um `Check` e devolve uma máscara booleana
com as linhas que falham. O mesmo catálogo serve para:
  * gerar o relatório de qualidade sobre os dados brutos;
  * garantir (nos testes e no pipeline) que os dados tratados passam em todas as regras.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .config import REFERENCE_DATE, Paths

Tables = dict[str, pd.DataFrame]

DATE_COLUMNS = {
    "customers": ["birth_date", "account_open_date"],
    "policies": ["start_date", "cancel_date"],
    "claims": ["claim_date"],
    "journey_events": ["event_ts"],
}

VALID_STATES = {"MG", "SP", "RJ", "BA", "PR", "RS", "PE", "CE", "GO", "DF", "SC", "ES", "PA", "AM",
                "AC", "AL", "AP", "MA", "MT", "MS", "PB", "PI", "RN", "RO", "RR", "SE", "TO"}


@dataclass(frozen=True)
class Check:
    name: str
    table: str
    dimension: str  # completude, unicidade, validade, consistência, integridade
    severity: str   # "bloqueante" (linha vai para quarentena) ou "alerta" (linha é corrigida)
    description: str
    rule: Callable[[Tables], pd.Series]


def load_raw(paths: Paths) -> Tables:
    tables = {}
    for name in ["customers", "products", "policies", "claims", "journey_events"]:
        df = pd.read_csv(paths.raw / f"{name}.csv")
        for col in DATE_COLUMNS.get(name, []):
            df[col] = pd.to_datetime(df[col])
        tables[name] = df
    return tables


def _policy_start(t: Tables) -> pd.Series:
    starts = t["policies"].drop_duplicates("policy_id").set_index("policy_id")["start_date"]
    return t["claims"]["policy_id"].map(starts)


CHECKS: list[Check] = [
    # Clientes
    Check("clientes_id_duplicado", "customers", "unicidade", "alerta",
          "customer_id repetido", lambda t: t["customers"]["customer_id"].duplicated(keep="first")),
    Check("clientes_uf_nula", "customers", "completude", "alerta",
          "UF não informada", lambda t: t["customers"]["state"].isna()),
    Check("clientes_uf_invalida", "customers", "validade", "alerta",
          "UF fora do padrão (minúscula, espaços ou sigla inexistente)",
          lambda t: t["customers"]["state"].notna() & ~t["customers"]["state"].isin(VALID_STATES | {"ND"})),
    Check("clientes_nascimento_futuro", "customers", "validade", "alerta",
          "data de nascimento posterior à data de referência",
          lambda t: t["customers"]["birth_date"] > pd.Timestamp(REFERENCE_DATE)),
    # Apólices
    Check("apolices_id_duplicado", "policies", "unicidade", "alerta",
          "policy_id repetido", lambda t: t["policies"]["policy_id"].duplicated(keep="first")),
    Check("apolices_premio_nao_positivo", "policies", "validade", "bloqueante",
          "prêmio mensal menor ou igual a zero", lambda t: t["policies"]["monthly_premium"] <= 0),
    Check("apolices_cancelamento_antes_inicio", "policies", "consistência", "bloqueante",
          "data de cancelamento anterior ao início de vigência",
          lambda t: t["policies"]["cancel_date"] < t["policies"]["start_date"]),
    Check("apolices_status_inconsistente", "policies", "consistência", "bloqueante",
          "status 'cancelada' sem data de cancelamento (ou o inverso)",
          lambda t: (t["policies"]["status"] == "cancelada") != t["policies"]["cancel_date"].notna()),
    Check("apolices_cliente_orfao", "policies", "integridade", "bloqueante",
          "customer_id inexistente na base de clientes",
          lambda t: ~t["policies"]["customer_id"].isin(t["customers"]["customer_id"])),
    # Sinistros
    Check("sinistros_apolice_orfa", "claims", "integridade", "bloqueante",
          "policy_id inexistente na base de apólices",
          lambda t: ~t["claims"]["policy_id"].isin(t["policies"]["policy_id"])),
    Check("sinistros_antes_vigencia", "claims", "consistência", "bloqueante",
          "sinistro com data anterior ao início da apólice",
          lambda t: t["claims"]["claim_date"] < _policy_start(t)),
    Check("sinistros_pago_maior_que_avisado", "claims", "consistência", "bloqueante",
          "valor pago maior que o valor avisado",
          lambda t: t["claims"]["paid_amount"] > t["claims"]["claim_amount"]),
    Check("sinistros_pago_sem_aprovacao", "claims", "consistência", "bloqueante",
          "pagamento registrado para sinistro não aprovado",
          lambda t: (t["claims"]["claim_status"] != "aprovado") & (t["claims"]["paid_amount"] > 0)),
    # Jornada
    Check("jornada_evento_futuro", "journey_events", "validade", "bloqueante",
          "evento posterior à data de referência",
          lambda t: t["journey_events"]["event_ts"].dt.normalize() > pd.Timestamp(REFERENCE_DATE)),
    Check("jornada_produto_invalido", "journey_events", "integridade", "bloqueante",
          "product_id inexistente no catálogo",
          lambda t: ~t["journey_events"]["product_id"].isin(t["products"]["product_id"])),
]


def run_checks(tables: Tables, checks: list[Check] = CHECKS) -> pd.DataFrame:
    """Executa todas as regras e devolve um resumo por regra."""
    rows = []
    for c in checks:
        mask = c.rule(tables).fillna(False).astype(bool)
        total = len(tables[c.table])
        failed = int(mask.sum())
        rows.append({
            "regra": c.name, "tabela": c.table, "dimensao": c.dimension, "severidade": c.severity,
            "descricao": c.description, "linhas_avaliadas": total, "linhas_com_falha": failed,
            "pct_falha": round(failed / total, 5) if total else 0.0,
            "status": "OK" if failed == 0 else "FALHA",
        })
    return pd.DataFrame(rows)


def failing_rows(tables: Tables, table: str, severity: str | None = None) -> pd.DataFrame:
    """Linhas de uma tabela que falham em pelo menos uma regra, com o motivo concatenado."""
    df = tables[table]
    reasons = pd.Series("", index=df.index)
    for c in CHECKS:
        if c.table != table or (severity and c.severity != severity):
            continue
        mask = c.rule(tables).fillna(False).astype(bool)
        reasons[mask] = reasons[mask] + c.name + ";"
    out = df[reasons != ""].copy()
    out["motivo"] = reasons[reasons != ""].str.rstrip(";")
    return out


def write_report(summary: pd.DataFrame, paths: Paths, filename: str = "qualidade_dados.md") -> None:
    paths.ensure()
    summary.to_csv(paths.reports / filename.replace(".md", ".csv"), index=False)
    failed = summary[summary["status"] == "FALHA"]
    lines = [
        "# Relatório de qualidade de dados (base bruta)",
        "",
        f"Regras avaliadas: **{len(summary)}** · com falha: **{len(failed)}** · "
        f"linhas afetadas: **{int(summary['linhas_com_falha'].sum()):,}**".replace(",", "."),
        "",
        summary.drop(columns=["linhas_avaliadas"]).to_markdown(index=False),
        "",
        "Regras **bloqueantes** enviam a linha para `data/quarantine/`; regras de **alerta** são corrigidas no ETL "
        "(deduplicação e padronização).",
    ]
    (paths.reports / filename).write_text("\n".join(lines), encoding="utf-8")
