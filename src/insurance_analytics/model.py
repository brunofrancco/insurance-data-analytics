"""Modelo de propensão a cancelamento em 12 meses.

* Base analítica (ABT) montada em SQL a partir do data mart.
* Validação fora do tempo (out-of-time): treino com contratações mais antigas,
  teste com as mais recentes — simula o uso real do modelo.
* Regressão logística como modelo principal (interpretável) e gradient boosting
  como benchmark. Odds ratios estimados com statsmodels para leitura de negócio.
"""
from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import charts
from .config import SQL_DIR, Paths
from .kpis import default_params, read_sql_file

TARGET = "cancelou_12m"
CATEGORICAL = ["produto", "canal", "meio_pagamento", "faixa_renda", "segmento", "regiao", "genero"]
NUMERIC = ["idade", "premio_relativo", "produtos_na_contratacao", "meses_de_conta"]
TEST_START = "2024-07-01"  # contratações a partir desta data formam a base de teste


def load_abt(paths: Paths) -> pd.DataFrame:
    with sqlite3.connect(paths.warehouse) as con:
        return read_sql_file(SQL_DIR / "abt_cancelamento.sql", con, default_params())


def split_out_of_time(abt: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    is_test = abt["data_inicio"] >= TEST_START
    return abt[~is_test], abt[is_test]


def build_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CATEGORICAL),
    ])
    return Pipeline([("pre", pre), ("model", estimator)])


def lift_table(y_true: pd.Series, score: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Decil 1 = 10% com maior score."""
    df = pd.DataFrame({"y": np.asarray(y_true), "score": score})
    df["decil"] = pd.qcut(df["score"].rank(method="first", ascending=False), n_bins, labels=range(1, n_bins + 1))
    out = df.groupby("decil", observed=True).agg(apolices=("y", "size"), cancelamentos=("y", "sum"),
                                                 score_medio=("score", "mean"))
    out["taxa_cancelamento"] = out["cancelamentos"] / out["apolices"]
    out["lift"] = out["taxa_cancelamento"] / df["y"].mean()
    out["captura_acumulada"] = out["cancelamentos"].cumsum() / df["y"].sum()
    return out.reset_index()


def odds_ratios(train: pd.DataFrame) -> pd.DataFrame:
    """Logit com statsmodels: efeito de cada variável na chance de cancelar, com IC 95% e p-valor."""
    d = train.copy()
    d["idade"] = d["idade"].fillna(d["idade"].median())
    d["meses_de_conta"] = d["meses_de_conta"].fillna(d["meses_de_conta"].median())
    formula = (f"{TARGET} ~ C(produto, Treatment('Vida')) + C(canal, Treatment('app')) "
               "+ C(meio_pagamento, Treatment('debito_conta')) + C(faixa_renda) + idade "
               "+ premio_relativo + produtos_na_contratacao + meses_de_conta")
    fit = smf.logit(formula, data=d).fit(disp=False)
    ci = fit.conf_int()
    out = pd.DataFrame({
        "variavel": fit.params.index, "odds_ratio": np.exp(fit.params.values),
        "ic95_inf": np.exp(ci[0].values), "ic95_sup": np.exp(ci[1].values), "p_valor": fit.pvalues.values,
    })
    out["variavel"] = out["variavel"].str.replace(r"C\((\w+)(?:, Treatment\('\w+'\))?\)\[T\.(.+)\]", r"\1=\2", regex=True)
    return out[out["variavel"] != "Intercept"].sort_values("odds_ratio", ascending=False).round(4)


def train_and_evaluate(paths: Paths) -> dict:
    abt = load_abt(paths)
    train, test = split_out_of_time(abt)
    X_cols = CATEGORICAL + NUMERIC
    models = {
        "Regressão logística": build_pipeline(LogisticRegression(max_iter=2000, C=1.0)),
        "Gradient boosting": build_pipeline(HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05,
                                                                           max_iter=300, random_state=42)),
    }
    results, curves, scores = {}, {}, {}
    for name, pipe in models.items():
        pipe.fit(train[X_cols], train[TARGET])
        p = pipe.predict_proba(test[X_cols])[:, 1]
        fpr, tpr, _ = roc_curve(test[TARGET], p)
        auc = roc_auc_score(test[TARGET], p)
        curves[name] = (fpr, tpr, auc)
        scores[name] = p
        results[name] = {"auc": round(auc, 4), "average_precision": round(average_precision_score(test[TARGET], p), 4),
                         "brier": round(brier_score_loss(test[TARGET], p), 4)}

    main = "Regressão logística"
    lift = lift_table(test[TARGET], scores[main])
    top = lift.iloc[0]
    metrics = {
        "modelo_principal": main,
        "linhas_treino": len(train), "linhas_teste": len(test),
        "taxa_base_treino": round(train[TARGET].mean(), 4), "taxa_base_teste": round(test[TARGET].mean(), 4),
        "auc_teste": results[main]["auc"], "lift_top_decil": round(float(top["lift"]), 2),
        "captura_top_decil": round(float(top["captura_acumulada"]), 4),
        "comparacao_modelos": results,
    }
    paths.ensure()
    (paths.reports / "modelo_metricas.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    lift.round(4).to_csv(paths.reports / "modelo_lift_decil.csv", index=False)
    odds_ratios(train).to_csv(paths.reports / "modelo_odds_ratios.csv", index=False)
    charts.roc_curves(curves, paths.figures / "modelo_roc.png")
    charts.lift_by_decile(lift, test[TARGET].mean(), paths.figures / "modelo_lift_decil.png")
    return metrics
