import pandas as pd

from insurance_analytics import data_quality as dq
from insurance_analytics.etl import clean


def test_raw_data_has_injected_issues(pipeline_output):
    _, result = pipeline_output
    failed = set(result["dq"].query("status == 'FALHA'")["regra"])
    assert {"clientes_id_duplicado", "apolices_premio_nao_positivo", "sinistros_antes_vigencia"} <= failed


def test_cleaned_data_passes_every_rule(pipeline_output):
    paths, _ = pipeline_output
    cleaned, quarantine = clean(dq.load_raw(paths))
    summary = dq.run_checks(cleaned)
    assert (summary["status"] == "OK").all(), summary[summary["status"] != "OK"]
    assert all("motivo" in q.columns for q in quarantine.values())


def test_rule_flags_exact_rows():
    tables = {
        "customers": pd.DataFrame({"customer_id": [1, 2]}),
        "policies": pd.DataFrame({
            "policy_id": [10, 11, 12], "customer_id": [1, 2, 3], "monthly_premium": [10.0, -5.0, 20.0],
            "start_date": pd.to_datetime(["2024-01-01"] * 3), "cancel_date": pd.to_datetime([None, None, None]),
            "status": ["ativa"] * 3,
        }),
    }
    out = dq.failing_rows(tables, "policies", severity="bloqueante")
    assert out["policy_id"].tolist() == [11, 12]
    assert out.set_index("policy_id").loc[11, "motivo"] == "apolices_premio_nao_positivo"
    assert out.set_index("policy_id").loc[12, "motivo"] == "apolices_cliente_orfao"
