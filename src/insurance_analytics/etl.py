"""ETL: trata os dados brutos e carrega o modelo dimensional em SQLite."""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from .config import REFERENCE_DATE, SQL_DIR, Paths
from .data_quality import VALID_STATES, Tables, failing_rows

REF = pd.Timestamp(REFERENCE_DATE)

REGIONS = {
    "Sudeste": ["MG", "SP", "RJ", "ES"], "Sul": ["PR", "RS", "SC"],
    "Nordeste": ["BA", "PE", "CE", "AL", "MA", "PB", "PI", "RN", "SE"],
    "Centro-Oeste": ["GO", "DF", "MT", "MS"], "Norte": ["PA", "AM", "AC", "AP", "RO", "RR", "TO"],
}
STATE_TO_REGION = {uf: region for region, ufs in REGIONS.items() for uf in ufs}
CHANNEL_KEYS = {"app": 1, "internet_banking": 2, "parceiro": 3}


def date_key(s: pd.Series) -> pd.Series:
    """Converte datas em chave inteira yyyymmdd (nulos preservados)."""
    return pd.to_numeric(s.dt.strftime("%Y%m%d"), errors="coerce").astype("Int64")


# --------------------------------------------------------------------------- limpeza
def clean(raw: Tables) -> tuple[Tables, Tables]:
    """Corrige o que é corrigível e separa em quarentena o que viola regras bloqueantes.

    A ordem importa: apólices são validadas contra clientes já tratados e sinistros
    contra apólices já tratadas, para que órfãos gerados pela quarentena também saiam.
    """
    t = dict(raw)
    cust = t["customers"].drop_duplicates("customer_id").copy()
    cust["state"] = cust["state"].str.strip().str.upper()
    cust.loc[~cust["state"].isin(VALID_STATES), "state"] = "ND"
    cust.loc[cust["birth_date"] > REF, "birth_date"] = pd.NaT
    t["customers"] = cust
    t["policies"] = t["policies"].drop_duplicates("policy_id")

    quarantine = {}
    for table in ["policies", "claims", "journey_events"]:
        bad = failing_rows(t, table, severity="bloqueante")
        quarantine[table] = bad
        t[table] = t[table].drop(index=bad.index)
    return t, quarantine


# --------------------------------------------------------------------------- dimensões
def build_dim_date(start: str = "2018-01-01") -> pd.DataFrame:
    d = pd.Series(pd.date_range(start, REF, freq="D"))
    return pd.DataFrame({
        "date_key": date_key(d), "full_date": d.dt.strftime("%Y-%m-%d"), "year": d.dt.year,
        "quarter": d.dt.quarter, "month": d.dt.month, "year_month": d.dt.strftime("%Y-%m"),
        "day_of_week": d.dt.dayofweek, "is_weekend": (d.dt.dayofweek >= 5).astype(int),
    })


def build_dim_customer(cust: pd.DataFrame) -> pd.DataFrame:
    age = ((REF - cust["birth_date"]).dt.days // 365.25).astype("Int64")
    age_band = pd.cut(age.astype(float), [17, 24, 34, 44, 54, 200], labels=["18-24", "25-34", "35-44", "45-54", "55+"])
    return pd.DataFrame({
        "customer_key": cust["customer_id"], "gender": cust["gender"], "state": cust["state"],
        "region": cust["state"].map(STATE_TO_REGION).fillna("ND"), "income_band": cust["income_band"],
        "segment": cust["segment"], "age": age, "age_band": age_band.astype(str).replace("nan", "ND"),
        "account_open_date_key": date_key(cust["account_open_date"]),
    })


def build_dim_channel() -> pd.DataFrame:
    return pd.DataFrame({
        "channel_key": list(CHANNEL_KEYS.values()), "channel_name": list(CHANNEL_KEYS.keys()),
        "channel_type": ["digital", "digital", "parceiro"],
    })


# --------------------------------------------------------------------------- fatos
def build_fact_policy(pol: pd.DataFrame, cust: pd.DataFrame) -> pd.DataFrame:
    birth = pol["customer_id"].map(cust.set_index("customer_id")["birth_date"])
    end = pol["cancel_date"].fillna(REF + pd.Timedelta(days=1))
    return pd.DataFrame({
        "policy_id": pol["policy_id"], "customer_key": pol["customer_id"], "product_key": pol["product_id"],
        "channel_key": pol["channel"].map(CHANNEL_KEYS), "start_date_key": date_key(pol["start_date"]),
        "cancel_date_key": date_key(pol["cancel_date"]), "payment_method": pol["payment_method"],
        "status": pol["status"], "monthly_premium": pol["monthly_premium"],
        "customer_age_at_start": ((pol["start_date"] - birth).dt.days // 365.25).astype("Int64"),
        "tenure_days": (end - pol["start_date"]).dt.days,
    })


def build_fact_policy_month(pol: pd.DataFrame) -> pd.DataFrame:
    """Explode cada apólice em meses de vigência e calcula o prêmio ganho pro rata die."""
    start = pol["start_date"]
    end_excl = pol["cancel_date"].fillna(REF + pd.Timedelta(days=1))  # primeiro dia sem cobertura
    # O mês do cancelamento sempre tem linha (mesmo com exposição zero), para registrar o evento.
    last_month = pol["cancel_date"].fillna(REF)
    n_months = (last_month.dt.year - start.dt.year) * 12 + (last_month.dt.month - start.dt.month) + 1

    rep = pol.loc[pol.index.repeat(n_months)].copy()
    k = rep.groupby(level=0).cumcount().to_numpy()
    month_start = pd.to_datetime(
        (rep["start_date"].to_numpy().astype("datetime64[M]") + k.astype("timedelta64[M]")).astype("datetime64[D]")
    )
    next_month = month_start + pd.offsets.MonthBegin(1)
    rep_end = end_excl.loc[rep.index].to_numpy()
    cover_from = np.maximum(rep["start_date"].to_numpy(), month_start.to_numpy())
    cover_to = np.minimum(rep_end, next_month.to_numpy())
    exposure = np.clip((cover_to - cover_from).astype("timedelta64[D]").astype(int), 0, None)

    cancelled = rep["cancel_date"].notna().to_numpy()
    cancel_in_month = cancelled & (rep["cancel_date"].to_numpy() >= month_start.to_numpy()) & (
        rep["cancel_date"].to_numpy() < next_month.to_numpy())
    return pd.DataFrame({
        "policy_id": rep["policy_id"].to_numpy(),
        "month_key": date_key(pd.Series(month_start)).to_numpy(),
        "customer_key": rep["customer_id"].to_numpy(), "product_key": rep["product_id"].to_numpy(),
        "channel_key": rep["channel"].map(CHANNEL_KEYS).to_numpy(), "months_since_start": k,
        "exposure_days": exposure,
        "earned_premium": np.round(rep["monthly_premium"].to_numpy() * exposure / month_start.days_in_month.to_numpy(), 2),
        "is_new": (k == 0).astype(int), "is_cancelled": cancel_in_month.astype(int),
        "is_active_eom": (rep_end >= next_month.to_numpy()).astype(int),
    })


def build_fact_claim(clm: pd.DataFrame, pol: pd.DataFrame) -> pd.DataFrame:
    p = pol.set_index("policy_id")
    start = clm["policy_id"].map(p["start_date"])
    return pd.DataFrame({
        "claim_id": clm["claim_id"], "policy_id": clm["policy_id"],
        "customer_key": clm["policy_id"].map(p["customer_id"]), "product_key": clm["policy_id"].map(p["product_id"]),
        "claim_date_key": date_key(clm["claim_date"]), "claim_status": clm["claim_status"],
        "claim_amount": clm["claim_amount"], "paid_amount": clm["paid_amount"],
        "days_since_start": (clm["claim_date"] - start).dt.days,
    })


def build_fact_funnel(ev: pd.DataFrame) -> pd.DataFrame:
    order = {"oferta_visualizada": 0, "simulacao": 1, "proposta": 2, "contratacao": 3}
    return pd.DataFrame({
        "event_id": ev["event_id"], "session_id": ev["session_id"], "customer_key": ev["customer_id"],
        "product_key": ev["product_id"], "channel_key": ev["channel"].map(CHANNEL_KEYS),
        "date_key": date_key(ev["event_ts"]), "step": ev["step"], "step_order": ev["step"].map(order),
        "event_ts": ev["event_ts"].dt.strftime("%Y-%m-%d %H:%M:%S"),
    })


def build_star(t: Tables) -> Tables:
    products = t["products"]
    return {
        "dim_date": build_dim_date(),
        "dim_customer": build_dim_customer(t["customers"]),
        "dim_product": products.rename(columns={"product_id": "product_key"}),
        "dim_channel": build_dim_channel(),
        "fact_policy": build_fact_policy(t["policies"], t["customers"]),
        "fact_policy_month": build_fact_policy_month(t["policies"]),
        "fact_claim": build_fact_claim(t["claims"], t["policies"]),
        "fact_funnel_event": build_fact_funnel(t["journey_events"]),
    }


def load(star: Tables, paths: Paths) -> None:
    paths.ensure()
    with sqlite3.connect(paths.warehouse) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        for name, df in star.items():  # dimensões primeiro (ordem do dicionário)
            df.to_sql(name, con, if_exists="append", index=False, chunksize=50_000)


def run(raw: Tables, paths: Paths) -> tuple[Tables, Tables]:
    cleaned, quarantine = clean(raw)
    for table, df in quarantine.items():
        df.to_csv(paths.quarantine / f"{table}.csv", index=False)
    star = build_star(cleaned)
    load(star, paths)
    return cleaned, star
