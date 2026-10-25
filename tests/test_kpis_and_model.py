import numpy as np
import pandas as pd

from insurance_analytics.model import lift_table


def test_all_kpis_return_rows(pipeline_output):
    _, result = pipeline_output
    for name, df in result["kpis"].items():
        assert len(df) > 0, name


def test_rates_are_between_zero_and_one(pipeline_output):
    _, result = pipeline_output
    k = result["kpis"]
    for name, cols in {
        "cancelamento_12m": ["taxa_cancelamento_12m"],
        "funil_conversao": ["conv_oferta_simulacao", "conv_simulacao_proposta", "conversao_total"],
        "retencao_coorte": ["retencao"],
        "cross_sell": ["pct_clientes"],
    }.items():
        assert k[name][cols].apply(lambda s: s.between(0, 1)).all().all(), name


def test_funnel_is_monotonic(pipeline_output):
    _, result = pipeline_output
    f = result["kpis"]["funil_conversao"]
    assert (f["ofertas_visualizadas"] >= f["simulacoes"]).all()
    assert (f["simulacoes"] >= f["propostas"]).all()
    assert (f["propostas"] >= f["contratacoes"]).all()


def test_shares_sum_to_one(pipeline_output):
    _, result = pipeline_output
    assert abs(result["kpis"]["cross_sell"]["pct_clientes"].sum() - 1) < 1e-3
    assert abs(result["kpis"]["carteira_regiao"]["participacao_premio"].sum() - 1) < 1e-3


def test_model_beats_random(pipeline_output):
    _, result = pipeline_output
    assert result["metrics"]["auc_teste"] > 0.6
    assert result["metrics"]["lift_top_decil"] > 1.3


def test_lift_table_perfect_score():
    y = pd.Series([1] * 10 + [0] * 90)
    out = lift_table(y, np.linspace(1, 0, 100))
    assert out.loc[0, "taxa_cancelamento"] == 1.0
    assert out.loc[0, "lift"] == 10.0
    assert out["captura_acumulada"].iloc[-1] == 1.0


def test_reports_written(pipeline_output):
    paths, _ = pipeline_output
    for f in ["relatorio_executivo.html", "relatorio_kpis.xlsx", "qualidade_dados.md", "modelo_metricas.json"]:
        assert (paths.reports / f).exists(), f
