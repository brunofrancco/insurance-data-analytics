"""Gera dados sintéticos de uma seguradora digital (clientes, apólices, sinistros e jornada).

Os dados imitam a operação de uma seguradora que vende pelo app de um banco digital.
As regras de negócio (sinistralidade por produto, risco de cancelamento, funil de
conversão) são embutidas de propósito para que as análises e o modelo encontrem
padrões reais. Também injetamos problemas de qualidade típicos de produção
(duplicidades, nulos, órfãos, datas inválidas) para exercitar a camada de validação.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import REFERENCE_DATE, START_DATE, Paths

STATES = ["MG", "SP", "RJ", "BA", "PR", "RS", "PE", "CE", "GO", "DF", "SC", "ES", "PA", "AM"]
STATE_WEIGHTS = [0.22, 0.24, 0.10, 0.06, 0.06, 0.05, 0.05, 0.04, 0.04, 0.04, 0.04, 0.03, 0.02, 0.01]

INCOME_BANDS = ["ate_2k", "2k_5k", "5k_10k", "10k_mais"]
INCOME_WEIGHTS = [0.35, 0.38, 0.18, 0.09]
INCOME_PREMIUM_FACTOR = {"ate_2k": 0.85, "2k_5k": 1.0, "5k_10k": 1.2, "10k_mais": 1.5}

PRODUCTS = pd.DataFrame(
    [
        # id, nome, categoria, prêmio base mensal, frequência anual de sinistro, sinistralidade alvo, peso de venda, risco base de cancelamento (mensal)
        (1, "Vida", "Pessoas", 39.90, 0.010, 0.35, 0.22, 0.010),
        (2, "Residencial", "Patrimonial", 24.90, 0.050, 0.30, 0.18, 0.012),
        (3, "Auto", "Auto", 189.90, 0.120, 0.65, 0.12, 0.018),
        (4, "Celular", "Patrimonial", 29.90, 0.150, 0.55, 0.26, 0.025),
        (5, "Viagem", "Pessoas", 19.90, 0.050, 0.25, 0.08, 0.040),
        (6, "Pet", "Pessoas", 49.90, 0.600, 0.70, 0.14, 0.020),
    ],
    columns=[
        "product_id", "product_name", "category", "base_premium",
        "claim_frequency", "target_loss_ratio", "sales_weight", "base_cancel_hazard",
    ],
)

CHANNELS = ["app", "internet_banking", "parceiro"]
CHANNEL_WEIGHTS = [0.70, 0.20, 0.10]
PAYMENT_METHODS = ["cartao_credito", "debito_conta", "pix"]
PAYMENT_WEIGHTS = [0.50, 0.35, 0.15]

FUNNEL_STEPS = ["oferta_visualizada", "simulacao", "proposta", "contratacao"]


def _random_dates(rng: np.random.Generator, start, end, n: int) -> pd.Series:
    """Datas uniformes (granularidade de dia) entre start e end; ambos podem ser escalares ou séries."""
    to_days = lambda x: np.asarray(pd.to_datetime(x), dtype="datetime64[D]").astype(np.int64)  # noqa: E731
    start_d = np.broadcast_to(to_days(start), n)
    end_d = np.broadcast_to(to_days(end), n)
    days = start_d + (rng.random(n) * (end_d - start_d)).astype(np.int64)
    return pd.Series(pd.to_datetime(days.astype("datetime64[D]")))


def generate_customers(rng: np.random.Generator, n: int) -> pd.DataFrame:
    ref = pd.Timestamp(REFERENCE_DATE)
    age = np.clip(rng.normal(37, 12, n), 18, 80).astype(int)
    birth = ref - pd.to_timedelta(age * 365.25 + rng.integers(0, 365, n), unit="D")
    income = rng.choice(INCOME_BANDS, n, p=INCOME_WEIGHTS)
    segment = np.where(
        income == "10k_mais", "Premium", np.where(income == "5k_10k", rng.choice(["Plus", "Premium"], n, p=[0.7, 0.3]), "Essencial")
    )
    return pd.DataFrame(
        {
            "customer_id": np.arange(1, n + 1),
            "birth_date": birth.normalize(),
            "gender": rng.choice(["F", "M"], n),
            "state": rng.choice(STATES, n, p=STATE_WEIGHTS),
            "income_band": income,
            "segment": segment,
            "account_open_date": _random_dates(rng, pd.Timestamp("2018-01-01"), ref, n),
        }
    )


def generate_policies(rng: np.random.Generator, customers: pd.DataFrame) -> pd.DataFrame:
    ref = pd.Timestamp(REFERENCE_DATE)
    n_products = np.clip(1 + rng.poisson(0.45, len(customers)), 1, 4)
    rows = []
    weights = PRODUCTS["sales_weight"].to_numpy()
    for cid, k in zip(customers["customer_id"], n_products):
        chosen = rng.choice(PRODUCTS["product_id"], size=k, replace=False, p=weights / weights.sum())
        rows.extend((cid, pid, k) for pid in chosen)
    pol = pd.DataFrame(rows, columns=["customer_id", "product_id", "customer_n_products"])
    pol = pol.merge(customers[["customer_id", "birth_date", "income_band", "account_open_date"]], on="customer_id")
    pol = pol.merge(PRODUCTS, on="product_id")

    n = len(pol)
    earliest = pol["account_open_date"].where(pol["account_open_date"] > pd.Timestamp(START_DATE), pd.Timestamp(START_DATE))
    pol["start_date"] = _random_dates(rng, earliest, ref, n).values
    pol["channel"] = rng.choice(CHANNELS, n, p=CHANNEL_WEIGHTS)
    pol["payment_method"] = rng.choice(PAYMENT_METHODS, n, p=PAYMENT_WEIGHTS)

    age = ((pol["start_date"] - pol["birth_date"]).dt.days / 365.25).to_numpy()
    age_factor = np.where(pol["product_name"].isin(["Vida", "Auto"]), 1 + np.abs(age - 40) / 60, 1.0)
    income_factor = pol["income_band"].map(INCOME_PREMIUM_FACTOR).to_numpy()
    pol["monthly_premium"] = np.round(pol["base_premium"] * age_factor * income_factor * rng.lognormal(0, 0.15, n), 2)

    # Risco mensal de cancelamento: depende de produto, meio de pagamento, idade, canal e vínculo.
    log_hazard = (
        np.log(pol["base_cancel_hazard"].to_numpy())
        + np.select([pol["payment_method"] == "pix", pol["payment_method"] == "cartao_credito"], [0.55, 0.15], 0.0)
        + np.where(age < 25, 0.45, np.where(age > 55, -0.25, 0.0))
        + np.where(pol["channel"] == "parceiro", 0.35, 0.0)
        - 0.25 * (pol["customer_n_products"].to_numpy() - 1)
        + 0.30 * np.log(pol["monthly_premium"] / pol["base_premium"]).to_numpy()
    )
    months_to_cancel = rng.exponential(1 / np.exp(log_hazard))
    cancel_date = pol["start_date"] + pd.to_timedelta(months_to_cancel * 30.44, unit="D")
    cancelled = cancel_date <= ref
    pol["status"] = np.where(cancelled, "cancelada", "ativa")
    pol["cancel_date"] = cancel_date.where(cancelled).dt.normalize()

    pol = pol.sort_values("start_date").reset_index(drop=True)
    pol.insert(0, "policy_id", np.arange(100001, 100001 + n))
    return pol[
        ["policy_id", "customer_id", "product_id", "channel", "payment_method",
         "start_date", "cancel_date", "status", "monthly_premium"]
    ]


def generate_claims(rng: np.random.Generator, policies: pd.DataFrame) -> pd.DataFrame:
    ref = pd.Timestamp(REFERENCE_DATE)
    pol = policies.merge(PRODUCTS[["product_id", "claim_frequency", "target_loss_ratio"]], on="product_id")
    end = pol["cancel_date"].fillna(ref)
    exposure_years = ((end - pol["start_date"]).dt.days.clip(lower=0) / 365.25).to_numpy()
    n_claims = rng.poisson(pol["claim_frequency"].to_numpy() * exposure_years)

    idx = np.repeat(np.arange(len(pol)), n_claims)
    c = pol.iloc[idx].reset_index(drop=True)
    c_end = end.iloc[idx].reset_index(drop=True)
    c["claim_date"] = _random_dates(rng, c["start_date"], c_end, len(c)).values

    # Severidade calibrada para que sinistros pagos / prêmio fique perto da sinistralidade alvo.
    mean_severity = c["target_loss_ratio"] * c["monthly_premium"] * 12 / c["claim_frequency"] / 0.8
    sigma = 0.9
    c["claim_amount"] = np.round(rng.lognormal(np.log(mean_severity) - sigma**2 / 2, sigma), 2)

    days_since = (ref - c["claim_date"]).dt.days.to_numpy()
    p_analysis = np.where(days_since < 30, 0.6, 0.02)
    u = rng.random(len(c))
    c["claim_status"] = np.where(u < p_analysis, "em_analise", np.where(u < p_analysis + 0.12, "negado", "aprovado"))
    paid_share = rng.uniform(0.85, 1.0, len(c))  # franquia / participação do segurado
    c["paid_amount"] = np.where(c["claim_status"] == "aprovado", np.round(c["claim_amount"] * paid_share, 2), 0.0)

    c = c.sort_values("claim_date").reset_index(drop=True)
    c.insert(0, "claim_id", np.arange(1, len(c) + 1))
    return c[["claim_id", "policy_id", "claim_date", "claim_amount", "claim_status", "paid_amount"]]


def generate_journey(rng: np.random.Generator, policies: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Eventos do funil digital. Toda apólice vendida em canal digital tem uma sessão convertida;
    sessões não convertidas são geradas com taxas de passagem por etapa."""
    digital = policies[policies["channel"].isin(["app", "internet_banking"])]
    converted = pd.DataFrame(
        {
            "customer_id": digital["customer_id"].to_numpy(),
            "product_id": digital["product_id"].to_numpy(),
            "channel": digital["channel"].to_numpy(),
            "session_date": digital["start_date"].to_numpy(),
            "last_step": 3,
        }
    )
    # Passagem por etapa sem conversão: produtos simples (Celular, Viagem) convertem mais.
    n_lost = len(converted) * 5
    product_ids = rng.choice(PRODUCTS["product_id"], n_lost, p=PRODUCTS["sales_weight"] / PRODUCTS["sales_weight"].sum())
    easy = np.isin(product_ids, [4, 5])
    p_sim = np.where(easy, 0.50, 0.38)
    p_prop = np.where(easy, 0.45, 0.35)
    u1, u2 = rng.random(n_lost), rng.random(n_lost)
    last_step = np.where(u1 > p_sim, 0, np.where(u2 > p_prop, 1, 2))
    lost = pd.DataFrame(
        {
            "customer_id": rng.choice(customers["customer_id"], n_lost),
            "product_id": product_ids,
            "channel": rng.choice(["app", "internet_banking"], n_lost, p=[0.78, 0.22]),
            "session_date": _random_dates(rng, pd.Timestamp(START_DATE), pd.Timestamp(REFERENCE_DATE), n_lost).values,
            "last_step": last_step,
        }
    )
    sessions = pd.concat([converted, lost], ignore_index=True).sort_values("session_date").reset_index(drop=True)
    sessions["session_id"] = np.arange(1, len(sessions) + 1)
    sessions["session_start"] = pd.to_datetime(sessions["session_date"]) + pd.to_timedelta(
        rng.integers(8 * 3600, 22 * 3600, len(sessions)), unit="s"
    )

    events = sessions.loc[sessions.index.repeat(sessions["last_step"] + 1)].copy()
    events["step_order"] = events.groupby("session_id").cumcount()
    events["step"] = np.array(FUNNEL_STEPS)[events["step_order"]]
    events["event_ts"] = events["session_start"] + pd.to_timedelta(
        events["step_order"] * rng.integers(30, 300, len(events)), unit="s"
    )
    events = events.reset_index(drop=True)
    events.insert(0, "event_id", np.arange(1, len(events) + 1))
    return events[["event_id", "session_id", "customer_id", "product_id", "channel", "step", "event_ts"]]


def inject_quality_issues(rng: np.random.Generator, tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Simula problemas comuns em dados de produção."""
    cust = tables["customers"].copy()
    pol = tables["policies"].copy()
    clm = tables["claims"].copy()

    def sample_idx(df: pd.DataFrame, frac: float) -> np.ndarray:
        return rng.choice(df.index, max(1, int(len(df) * frac)), replace=False)

    cust["state"] = cust["state"].astype(object)
    cust.loc[sample_idx(cust, 0.010), "state"] = None
    i = sample_idx(cust, 0.010)
    cust.loc[i, "state"] = " " + cust.loc[i, "state"].fillna("mg").str.lower() + " "
    cust.loc[sample_idx(cust, 0.002), "birth_date"] = pd.Timestamp("2031-05-10")
    cust = pd.concat([cust, cust.sample(frac=0.005, random_state=1)], ignore_index=True)

    pol.loc[sample_idx(pol, 0.002), "monthly_premium"] = -pol["monthly_premium"].abs()
    i = sample_idx(pol[pol["status"] == "cancelada"], 0.005)
    pol.loc[i, "cancel_date"] = pol.loc[i, "start_date"] - pd.Timedelta(days=15)
    pol.loc[sample_idx(pol, 0.001), "customer_id"] = 999_999
    pol = pd.concat([pol, pol.sample(frac=0.003, random_state=2)], ignore_index=True)

    pol_start = clm["policy_id"].map(tables["policies"].set_index("policy_id")["start_date"])
    i = sample_idx(clm, 0.003)
    clm.loc[i, "claim_date"] = pol_start.loc[i] - pd.Timedelta(days=40)
    i = sample_idx(clm[clm["claim_status"] == "aprovado"], 0.003)
    clm.loc[i, "paid_amount"] = clm.loc[i, "claim_amount"] * 1.5
    clm.loc[sample_idx(clm, 0.001), "policy_id"] = 1

    return {**tables, "customers": cust, "policies": pol, "claims": clm}


def generate(paths: Paths, n_customers: int = 20_000, seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    customers = generate_customers(rng, n_customers)
    policies = generate_policies(rng, customers)
    claims = generate_claims(rng, policies)
    journey = generate_journey(rng, policies, customers)
    products = PRODUCTS[["product_id", "product_name", "category", "base_premium"]]

    tables = inject_quality_issues(
        rng, {"customers": customers, "products": products, "policies": policies, "claims": claims, "journey_events": journey}
    )
    paths.ensure()
    for name, df in tables.items():
        df.to_csv(paths.raw / f"{name}.csv", index=False)
    return tables
