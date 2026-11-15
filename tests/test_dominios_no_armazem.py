"""Os domínios de valores contra o armazém (Bloco 5, Parte A, itens 2 e 3; ADR-0055).

Três guardas, que o `accepted_values` derivado não faz sozinho:

* **a cobertura** — toda coluna física de `analytics` e de `consumption`, lida do `information_schema`, tem
  exatamente uma classificação (`value_domains.coverage`): "N de N colunas classificadas";
* **a conta por ligação** — o `accepted_values` prova que o observado cabe no permitido; aqui se prova o
  outro lado: cada permitido que a coluna não tem está no `not_observed` dela, e nenhum `not_observed` é
  observado (a declaração atrasada também falha);
* **o membro desconhecido** — a linha de aterrissagem de cada dimensão declarada existe, e toda coluna de
  texto dela, e a chave natural, tem o sentinela que o catálogo declara.

As relações que os significados afirmam (item 4) ficam para o Bloco 5R: as que o dado de hoje contradiz
esperam a regeneração (Q27).
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, text

from mvp_ed1.db import WAREHOUSE, database_url
from mvp_ed1.models import descriptions
from mvp_ed1.models import value_domains as vd

pytestmark = pytest.mark.integracao

#: A chave do membro desconhecido: `dbt_utils.generate_surrogate_key(["'__desconhecido__'"])`
#: (macro `chave_desconhecida`), que é o `md5` do texto.
CHAVE_DESCONHECIDA = hashlib.md5(b"__desconhecido__").hexdigest()


@pytest.fixture(scope="module")
def engine():
    motor = create_engine(database_url(WAREHOUSE))
    try:
        with motor.connect() as conexao:
            conexao.execute(text("select 1 from analytics.dim_geography limit 1"))
    except Exception as erro:  # pragma: no cover — depende do ambiente
        motor.dispose()
        pytest.skip(f"armazém sem `analytics`: {erro}")
    yield motor
    motor.dispose()


@pytest.fixture(scope="module")
def catalogo() -> dict:
    return vd.load_catalog()


@pytest.fixture(scope="module")
def ligacoes() -> list[vd.Link]:
    return vd.links(descriptions.disk_entries())


def _schema(conexao, relacao: str) -> str:
    return conexao.execute(text(
        "select table_schema from information_schema.columns "
        "where table_schema in ('analytics', 'consumption') and table_name = :t limit 1"), {"t": relacao}).scalar_one()


def test_toda_coluna_fisica_tem_exatamente_uma_classificacao(engine, catalogo, ligacoes, record_property) -> None:
    with engine.connect() as conexao:
        colunas = conexao.execute(text(
            "select table_schema, table_name, column_name, data_type from information_schema.columns "
            "where table_schema in ('analytics', 'consumption') order by 1, 2, ordinal_position")).all()
    classificadas, problemas = vd.coverage(colunas, {(l.model, l.column) for l in ligacoes}, catalogo)
    record_property("colunas_classificadas", f"{len(classificadas)} de {len(colunas)}")
    assert problemas == []
    assert len(classificadas) == len(colunas)
    assert sum(1 for c in classificadas.values() if c == "value_domain") == len(ligacoes)


def test_cada_permitido_ausente_esta_no_not_observed_da_ligacao(engine, catalogo, ligacoes) -> None:
    divergencias = []
    with engine.connect() as conexao:
        conexao.execute(text("set transaction isolation level repeatable read read only"))
        for ligacao in ligacoes:
            schema = _schema(conexao, ligacao.model)
            observados = {r[0] for r in conexao.execute(text(
                f'select distinct "{ligacao.column}"::text from {schema}."{ligacao.model}" where "{ligacao.column}" is not null'))}
            permitidos = set(vd.allowed(ligacao, catalogo))
            if fora := sorted(observados - permitidos):
                divergencias.append(f"{ligacao.label}: fora do domínio {fora}")
            if (faltam := permitidos - observados) != set(ligacao.not_observed):
                divergencias.append(f"{ligacao.label}: ausentes {sorted(faltam)}, `not_observed` {sorted(ligacao.not_observed)}")
    assert divergencias == []


def test_a_linha_do_membro_desconhecido_tem_os_sentinelas_declarados(engine, catalogo) -> None:
    divergencias = []
    with engine.connect() as conexao:
        for dimensao, membro in catalogo["unknown_members"].items():
            chave = f"{dimensao.removeprefix('dim_')}_key"
            linha = conexao.execute(text(f"select * from analytics.{dimensao} where {chave} = :k"),
                                    {"k": CHAVE_DESCONHECIDA}).mappings().all()
            if len(linha) != 1:
                divergencias.append(f"{dimensao}: {len(linha)} linha(s) do membro desconhecido")
                continue
            linha = linha[0]
            esperadas = {c for c, v in linha.items() if (isinstance(v, str) and not c.endswith("_key"))
                         or c.endswith("_natural_key")}
            if esperadas != set(membro["columns"]):
                divergencias.append(f"{dimensao}: colunas de texto da linha {sorted(esperadas)}, declaradas {sorted(membro['columns'])}")
            for coluna, valor in membro["columns"].items():
                if str(linha.get(coluna)) != valor:
                    divergencias.append(f"{dimensao}.{coluna}: {linha.get(coluna)!r} na linha, {valor!r} declarado")
    assert divergencias == []
