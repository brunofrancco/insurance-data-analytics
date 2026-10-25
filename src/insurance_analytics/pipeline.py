"""Orquestra o fluxo completo: dados brutos → qualidade → data mart → KPIs → relatório → modelo.

Uso:
    python -m insurance_analytics.pipeline            # executa tudo
    python -m insurance_analytics.pipeline --skip-model
    python -m insurance_analytics.pipeline --customers 5000 --seed 7
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from . import data_quality, etl, kpis, model, report
from .config import PROJECT_ROOT, Paths
from .generate_data import generate

log = logging.getLogger("pipeline")


def run(paths: Paths, n_customers: int = 20_000, seed: int = 42, train_model: bool = True) -> dict:
    paths.ensure()
    t0 = time.perf_counter()

    log.info("1/5 Gerando dados brutos (%s clientes)", n_customers)
    generate(paths, n_customers=n_customers, seed=seed)

    log.info("2/5 Validando qualidade dos dados brutos")
    raw = data_quality.load_raw(paths)
    dq_summary = data_quality.run_checks(raw)
    data_quality.write_report(dq_summary, paths)
    log.info("    %d regras com falha", (dq_summary["status"] == "FALHA").sum())

    log.info("3/5 Tratando dados e carregando o data mart (%s)", paths.warehouse.name)
    cleaned, _ = etl.run(raw, paths)
    post = data_quality.run_checks(cleaned)
    if (post["status"] == "FALHA").any():
        raise RuntimeError(f"Dados tratados ainda violam regras:\n{post[post['status'] == 'FALHA']}")

    log.info("4/5 Calculando indicadores")
    k = kpis.run_all(paths)

    metrics = None
    if train_model:
        log.info("5/5 Treinando modelo de cancelamento")
        metrics = model.train_and_evaluate(paths)
        log.info("    AUC teste = %.3f | lift top decil = %.1fx", metrics["auc_teste"], metrics["lift_top_decil"])

    figs = report.build_figures(k, paths)
    report.write_excel(k, dq_summary, paths)
    report.write_html(k, dq_summary, figs, paths, metrics)
    log.info("Concluído em %.1fs. Relatórios em %s", time.perf_counter() - t0, paths.reports)
    return {"kpis": k, "dq": dq_summary, "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--customers", type=int, default=20_000, help="quantidade de clientes sintéticos")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="diretório raiz das saídas")
    parser.add_argument("--skip-model", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    run(Paths(args.root), args.customers, args.seed, train_model=not args.skip_model)


if __name__ == "__main__":
    main()
