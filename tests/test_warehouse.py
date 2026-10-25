"""Testes de integridade do modelo dimensional e de consistência entre fatos."""
import sqlite3

import pandas as pd
import pytest

from insurance_analytics.etl import build_fact_policy_month


@pytest.fixture(scope="module")
def con(pipeline_output):
    paths, _ = pipeline_output
    with sqlite3.connect(paths.warehouse) as c:
        yield c


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


@pytest.mark.parametrize("fact,fk,dim,pk", [
    ("fact_policy", "customer_key", "dim_customer", "customer_key"),
    ("fact_policy", "product_key", "dim_product", "product_key"),
    ("fact_policy", "start_date_key", "dim_date", "date_key"),
    ("fact_claim", "policy_id", "fact_policy", "policy_id"),
    ("fact_claim", "claim_date_key", "dim_date", "date_key"),
    ("fact_policy_month", "policy_id", "fact_policy", "policy_id"),
    ("fact_funnel_event", "product_key", "dim_product", "product_key"),
])
def test_no_orphan_foreign_keys(con, fact, fk, dim, pk):
    orphans = scalar(con, f"SELECT COUNT(*) FROM {fact} f LEFT JOIN {dim} d ON d.{pk} = f.{fk} WHERE d.{pk} IS NULL")
    assert orphans == 0


def test_snapshot_has_one_row_per_policy_month(con):
    assert scalar(con, "SELECT COUNT(*) - COUNT(DISTINCT policy_id || '-' || month_key) FROM fact_policy_month") == 0


def test_every_policy_starts_in_snapshot(con):
    assert scalar(con, "SELECT COUNT(*) FROM fact_policy") == scalar(con, "SELECT SUM(is_new) FROM fact_policy_month")


def test_active_policies_match_snapshot_last_month(con):
    active = scalar(con, "SELECT COUNT(*) FROM fact_policy WHERE status = 'ativa'")
    eom = scalar(con, "SELECT SUM(is_active_eom) FROM fact_policy_month WHERE month_key = 20251201")
    assert active == eom


def test_earned_premium_is_pro_rata():
    pol = pd.DataFrame({
        "policy_id": [1], "customer_id": [1], "product_id": [1], "channel": ["app"], "monthly_premium": [31.0],
        "start_date": pd.to_datetime(["2025-01-17"]), "cancel_date": pd.to_datetime(["2025-03-01"]),
    })
    m = build_fact_policy_month(pol)
    # jan: 15 de 31 dias; fev: mês inteiro; cancelada em 01/03 -> março registra o evento sem exposição
    assert m["exposure_days"].tolist() == [15, 28, 0]
    assert m["earned_premium"].tolist() == [15.0, 31.0, 0.0]
    assert m["is_active_eom"].tolist() == [1, 1, 0]
    assert m["is_cancelled"].tolist() == [0, 0, 1]
