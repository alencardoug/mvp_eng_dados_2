"""A chave de cada view de `consumption` é única no armazém (UQ-18 do BI).

A especificação do pacote ([Pacote §3](../docs/pacote_de_metadados.md)) diz que a chave de uma view é a
união das colunas de papel `grain` e `identity` em `view_rules`, e não `relations.*.grain`, que é `null`
nas views. Aqui ela é conferida no dado: nenhuma combinação dessas colunas se repete, numa transação
somente leitura. A chave sai da declaração (`metricas.yml`, por `models/metrics.py`), a mesma que o
pacote publica.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from mvp_ed1.db import WAREHOUSE, database_url
from mvp_ed1.models import metrics

pytestmark = pytest.mark.integracao

REGRAS = metrics.view_rules()


def chave(view: str) -> list[str]:
    return [c for c, papel in REGRAS[view]["columns"].items() if papel["role"] in ("grain", "identity")]


def test_toda_view_declara_uma_chave() -> None:
    assert len(REGRAS) == 16
    assert [v for v in REGRAS if not chave(v)] == []


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


@pytest.mark.parametrize("view", sorted(REGRAS))
def test_a_chave_da_view_e_unica(engine, view: str) -> None:
    colunas = ", ".join(chave(view))
    with engine.connect() as conexao:
        conexao.execute(text("begin transaction isolation level repeatable read read only"))
        linhas, repetidas = conexao.execute(text(
            f"select (select count(*) from {view}), "
            f"(select count(*) from (select 1 from {view} group by {colunas} having count(*) > 1) r)")).one()
        conexao.execute(text("rollback"))
    assert linhas > 0, f"{view} vazia: a unicidade não prova nada"
    assert repetidas == 0, f"{view}: {repetidas} combinações de ({colunas}) repetidas"
