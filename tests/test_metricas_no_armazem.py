"""As métricas declaradas contra as views auditadas (Bloco 5, Parte B, itens 6 a 8; ADR-0055).

O SQL de cada view sai **só** de `docs/glossario_de_negocio/metricas.yml`, pelo montador fixo
(`models/metrics.py`), e é comparado com a view, linha a linha, nos dois sentidos (`except all`), num corte
`REPEATABLE READ READ ONLY`. O resultado são dois números que não se somam: as colunas de medida e de métrica
**reproduzidas pela declaração**, e as **conferidas por referência** — a view que não cabe na forma aponta para
o teste do Bloco 1b que a compara inteira (`tests/test_auditoria_das_views.py`).

**O limite:** a comparação prova que a declaração e a view auditada dizem o mesmo. Se a declaração copiar a
leitura que a view faz da regra, um erro comum às duas fica — a independência continua sendo a das
referências do Bloco 1b e das conferências de população, que não mudam.
"""

from __future__ import annotations

import copy
import pathlib

import pytest
from sqlalchemy import create_engine, text

from mvp_ed1.db import WAREHOUSE, database_url
from mvp_ed1.models import metrics

pytestmark = pytest.mark.integracao

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DOC = metrics.load_catalog()
MONTADAS = sorted(n for n, v in DOC["views"].items() if "reference" not in v)


@pytest.fixture(scope="module")
def engine():
    motor = create_engine(database_url(WAREHOUSE))
    try:
        with motor.connect() as conexao:
            conexao.execute(text("select 1 from consumption.monthly_revenue_by_channel_and_category limit 1"))
    except Exception as erro:  # pragma: no cover — depende do ambiente
        motor.dispose()
        pytest.skip(f"armazém sem as views de consumo: {erro}")
    yield motor
    motor.dispose()


def _diferenca(conexao, doc: dict, view: str) -> tuple[int, int]:
    """(linhas só na montada, linhas só na view), num corte só."""
    colunas = ", ".join(doc["views"][view]["columns"])
    sql = metrics.assemble(doc, view)
    return tuple(conexao.execute(text(
        f"with m as ({sql}) select "
        f"(select count(*) from (select {colunas} from m except all select {colunas} from consumption.{view}) a), "
        f"(select count(*) from (select {colunas} from consumption.{view} except all select {colunas} from m) b)")).one())


@pytest.mark.parametrize("view", MONTADAS)
def test_a_declaracao_reproduz_a_view(engine, view: str) -> None:
    with engine.connect() as conexao:
        conexao.execute(text("set transaction isolation level repeatable read read only"))
        assert _diferenca(conexao, DOC, view) == (0, 0)


def test_as_duas_contas_nao_se_somam(record_property) -> None:
    reproduzidas = sum(1 for n in MONTADAS for c, p in DOC["views"][n]["columns"].items()
                       if metrics.role(c, p)[0] in ("measure", "metric"))
    por_referencia = sum(1 for v in DOC["views"].values() for c, p in v["columns"].items()
                         if metrics.role(c, p)[0] == "reference")
    record_property("reproduzidas_pela_declaracao", reproduzidas)
    record_property("conferidas_por_referencia", por_referencia)
    assert reproduzidas and por_referencia


def test_toda_coluna_de_toda_view_tem_papel(engine) -> None:
    """Item 8: o conjunto declarado é o da view — nem a mais, nem a menos, na mesma ordem."""
    views = sorted(p.stem for p in (RAIZ / "dbt" / "models" / "consumption").glob("*.sql"))
    assert sorted(DOC["views"]) == views
    with engine.connect() as conexao:
        for view in views:
            fisicas = [r[0] for r in conexao.execute(text(
                "select column_name from information_schema.columns where table_schema = 'consumption' "
                "and table_name = :v order by ordinal_position"), {"v": view})]
            assert list(DOC["views"][view]["columns"]) == fisicas, view


def test_a_referencia_citada_existe_e_e_a_do_bloco_1b() -> None:
    """Item 7: a view por referência aponta para a consulta que o teste do Bloco 1b compara com ela."""
    import yaml
    resultado = yaml.safe_load((RAIZ / "tests" / "auditoria" / "resultado.yml").read_text(encoding="utf-8"))["views"]
    teste = (RAIZ / "tests" / "test_auditoria_das_views.py").read_text(encoding="utf-8")
    for nome, view in DOC["views"].items():
        if "reference" not in view:
            continue
        ref = view["reference"]
        assert (RAIZ / ref["query"]).is_file(), nome
        assert resultado[nome]["reference"] == ref["query"], nome
        arquivo, _, funcao = ref["test"].partition("::")
        assert arquivo == "tests/test_auditoria_das_views.py" and f"def {funcao}(" in teste, nome


def _sem_filtro_de_pedido(d):
    for m in ("net_revenue_amount", "order_count"):
        d["measures"][m]["filters"] = []


def _data_da_conversao(d):
    d["sources"]["cart_events"]["date"]["column"] = "event_date_key"


def _sem_a_origem_na_categoria(d):
    juncao = next(j for j in d["sources"]["sale_dispatches"]["joins"] if j["alias"] == "cat")
    juncao["match"] = juncao["match"][1:]


def _capturas_sem_o_meio(d):
    v = d["views"]["refund_rate_by_reason"]
    v["sources"][1]["grain"] = ["year_month"]
    v["combine"]["keys"] = ["year_month"]


def _escala_um(d):
    d["metrics"]["discount_share_pct"]["scale"] = 1


def _uma_casa(d):
    d["metrics"]["cart_conversion_rate_pct"]["round"] = 1


@pytest.mark.parametrize("view, mudar", [
    ("average_order_value_by_channel_and_segment", _sem_filtro_de_pedido),
    ("cart_conversion_rate_by_channel", _data_da_conversao),
    ("gross_margin_by_category", _sem_a_origem_na_categoria),
    ("refund_rate_by_reason", _capturas_sem_o_meio),
    ("discount_share_by_channel", _escala_um),
    ("cart_conversion_rate_by_channel", _uma_casa),
], ids=lambda x: getattr(x, "__name__", x))
def test_a_contraprova_muda_so_a_declaracao_e_diverge(engine, view: str, mudar) -> None:
    """Item 6: com a view e as referências intactas, a declaração alterada tem de divergir."""
    doc = copy.deepcopy(DOC)
    mudar(doc)
    with engine.connect() as conexao:
        conexao.execute(text("set transaction isolation level repeatable read read only"))
        assert _diferenca(conexao, doc, view) != (0, 0)
