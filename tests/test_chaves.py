"""As chaves declaradas de `analytics` (Bloco 6, ADR-0056; F10).

Sem banco, sobre o *manifest*: todo modelo com contrato, toda coluna com `data_type`, uma PK por modelo e
ela é a chave substituta com `unique` e `not_null`, e toda `relationships` de `analytics` na forma que a
macro `instalar_chaves` transforma em FK. No armazém: o `pg_constraint` tem exatamente as 26 PKs e as 58 FKs
declaradas, validadas, e o tipo que cada modelo calcula é o declarado — o que o contrato não compara.
"""

from __future__ import annotations

import copy
import json

import pytest
from sqlalchemy import create_engine, text

from mvp_ed1.db import WAREHOUSE, database_url
from mvp_ed1.models import data_types as dt

#: O inventário medido no desenho (Bloco 6, "O que foi medido"): o oráculo das contagens.
MODELOS, COLUNAS, FKS = 26, 513, 58


def _manifest() -> dict:
    if not dt.MANIFEST.exists():
        pytest.skip("sem manifest; rode `make dbt-build`")
    return json.loads(dt.MANIFEST.read_text(encoding="utf-8"))


def _testes(manifest: dict, nome: str) -> list[dict]:
    return [t for t in manifest["nodes"].values()
            if t["resource_type"] == "test" and (t.get("test_metadata") or {}).get("name") == nome]


def declared_fks(manifest: dict) -> set[tuple[str, str, str, str]]:
    """(tabela, coluna, apontada, coluna apontada) de cada `relationships` de `analytics` — o que a macro instala."""
    modelos = dt.analytics_models(manifest)
    saida = set()
    for t in _testes(manifest, "relationships"):
        filho = manifest["nodes"].get(t.get("attached_node") or "", {})
        if filho.get("name") in modelos:
            kw = t["test_metadata"]["kwargs"]
            saida.add((filho["name"], t["column_name"], kw["to"].split("'")[1], kw["field"]))
    return saida


def declared_pks(manifest: dict) -> dict[str, list[str]]:
    return {nome: [c for c, v in no["columns"].items() if any(k["type"] == "primary_key" for k in v.get("constraints") or [])]
            for nome, no in dt.analytics_models(manifest).items()}


# ── Sem banco ───────────────────────────────────────────────────────────────────

def test_todo_modelo_de_analytics_tem_contrato_e_toda_coluna_um_tipo() -> None:
    modelos = dt.analytics_models(_manifest())
    assert len(modelos) == MODELOS
    assert [n for n, no in modelos.items() if not no["config"]["contract"]["enforced"]] == []
    sem_tipo = [f"{n}.{c}" for n, no in modelos.items() for c, v in no["columns"].items() if not v.get("data_type")]
    assert sem_tipo == [] and sum(len(no["columns"]) for no in modelos.values()) == COLUNAS


def test_uma_pk_por_modelo_e_ela_e_a_chave_substituta_testada() -> None:
    manifest = _manifest()
    pks = declared_pks(manifest)
    assert {n: c for n, c in pks.items() if len(c) != 1} == {}
    assert {n: c[0] for n, c in pks.items()} == dt.primary_keys(manifest)
    com = lambda nome: {(manifest["nodes"][t["attached_node"]]["name"], t["column_name"]) for t in _testes(manifest, nome)}
    unicos, nao_nulos = com("unique"), com("not_null")
    assert [n for n, c in pks.items() if (n, c[0]) not in unicos or (n, c[0]) not in nao_nulos] == []


def test_toda_relationships_de_analytics_vira_fk_de_analytics_para_analytics() -> None:
    """A macro só instala `relationships` de `analytics` para `analytics`, sem `where`, para a PK da apontada:
    a que fugir disso não vira FK calada — falha aqui."""
    manifest = _manifest()
    modelos = dt.analytics_models(manifest)
    pks = {n: c[0] for n, c in declared_pks(manifest).items()}
    fora = []
    for t in _testes(manifest, "relationships"):
        filho = manifest["nodes"].get(t.get("attached_node") or "", {})
        if filho.get("name") not in modelos:
            continue
        kw = t["test_metadata"]["kwargs"]
        alvo = kw["to"].split("'")
        if len(alvo) != 3 or alvo[1] not in modelos or pks.get(alvo[1]) != kw["field"] or t["config"].get("where"):
            fora.append(t["unique_id"])
    assert fora == []
    assert len(declared_fks(manifest)) == FKS


def test_a_guarda_de_tipo_aponta_a_escala_e_o_comprimento_trocados() -> None:
    """Contraprova da guarda de tipo, sem banco: o calculado com outra escala, outro comprimento ou sem a coluna
    declarada é apontado; o calculado igual ao declarado não."""
    manifest = _manifest()
    igual = {n: {c: dt.postgres_name(v["data_type"]) for c, v in no["columns"].items()} for n, no in dt.analytics_models(manifest).items()}
    assert dt.type_drift(igual, manifest) == []
    escala = next((n, c) for n, cols in igual.items() for c, tp in cols.items() if tp == "numeric(12,4)")
    texto = next((n, c) for n, cols in igual.items() for c, tp in cols.items() if tp == "character varying(20)")
    alterado = copy.deepcopy(igual)
    alterado[escala[0]][escala[1]] = "numeric(12,6)"
    alterado[texto[0]][texto[1]] = "character varying(40)"
    del alterado["dim_date"]["full_date"]
    apontadas = {d.split(":")[0] for d in dt.type_drift(alterado, manifest)}
    assert apontadas == {f"{escala[0]}.{escala[1]}", f"{texto[0]}.{texto[1]}", "dim_date.full_date"}


def test_o_tipo_por_alvo_e_o_nome_que_o_bigquery_aceita() -> None:
    """RVB6-1-01: o BigQuery recusa o tipo parametrizado no `cast` do contrato, e não tem `character varying`
    nem `timestamp with time zone`."""
    assert dt.yml_value("numeric(12,4)") == "{{ 'numeric(12,4)' if target.type != 'bigquery' else 'numeric' }}"
    assert dt.yml_value("character varying(20)").endswith("else 'string' }}")
    assert dt.yml_value("timestamp with time zone").endswith("else 'timestamp' }}")
    assert [dt.yml_value(t) for t in ("text", "bigint", "boolean", "numeric", "date", "integer")] == \
        ["text", "bigint", "boolean", "numeric", "date", "integer"]
    for tipo in ("numeric(12,4)", "character varying", "timestamp with time zone", "text"):
        assert dt.postgres_name(dt.yml_value(tipo)) == tipo


# ── No armazém ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    motor = create_engine(database_url(WAREHOUSE))
    try:
        with motor.connect() as conexao:
            conexao.execute(text("select 1 from analytics.dim_date limit 1"))
    except Exception as erro:  # pragma: no cover — depende do ambiente
        motor.dispose()
        pytest.skip(f"armazém sem `analytics`: {erro}")
    yield motor
    motor.dispose()


@pytest.mark.integracao
def test_o_armazem_tem_exatamente_as_chaves_declaradas_e_validadas(engine) -> None:
    """Pela definição, nunca pelo nome: o nome da PK do dbt oscila (`__dbt_tmp_pkey`, `…pkey1`)."""
    manifest = _manifest()
    with engine.connect() as c:
        linhas = c.execute(text("""
            select k.contype, r.relname, a.attname, coalesce(p.relname, ''), coalesce(b.attname, ''), k.convalidated
            from pg_constraint k
            join pg_class r on r.oid = k.conrelid
            join pg_attribute a on a.attrelid = k.conrelid and a.attnum = k.conkey[1]
            left join pg_class p on p.oid = k.confrelid
            left join pg_attribute b on b.attrelid = k.confrelid and b.attnum = k.confkey[1]
            where k.connamespace = 'analytics'::regnamespace and k.contype in ('p', 'f')
              and cardinality(k.conkey) = 1
        """)).all()
        compostas = c.execute(text("""select count(*) from pg_constraint where connamespace = 'analytics'::regnamespace
                                      and contype in ('p', 'f') and cardinality(conkey) <> 1""")).scalar()
    assert compostas == 0
    assert [l for l in linhas if not l[5]] == []
    pks = {(l[1], l[2]) for l in linhas if l[0] == "p"}
    fks = {(l[1], l[2], l[3], l[4]) for l in linhas if l[0] == "f"}
    assert pks == {(n, c[0]) for n, c in declared_pks(manifest).items()}
    assert fks == declared_fks(manifest)


@pytest.mark.integracao
def test_o_tipo_que_cada_modelo_calcula_e_o_declarado(engine) -> None:
    """O que o contrato não compara (precisão, escala, comprimento): o SQL compilado num `select` sem linhas,
    lido do cursor com o `typmod` — nunca do catálogo da tabela, que já mostra o tipo depois da coerção."""
    manifest = _manifest()
    with dt._conectar() as conexao:
        calculado = dt.computed_types(conexao, manifest)
    assert dt.type_drift(calculado, manifest) == []
