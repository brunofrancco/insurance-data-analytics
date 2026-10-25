import pytest

from insurance_analytics.config import Paths
from insurance_analytics.pipeline import run


@pytest.fixture(scope="session")
def pipeline_output(tmp_path_factory):
    """Executa o pipeline inteiro uma vez, com uma base pequena, num diretório temporário."""
    paths = Paths(tmp_path_factory.mktemp("run"))
    result = run(paths, n_customers=4_000, seed=123)
    return paths, result
