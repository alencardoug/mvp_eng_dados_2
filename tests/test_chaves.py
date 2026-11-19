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

#: O inventário medido no desenho (Bloco 6, "O que foi medido"): o oráculo das contagens. A
#: `dim_sku_location` (ADR-0057, Q75) soma um modelo, 12 colunas e as FKs para o armazém e o produto.
MODELOS, COLUNAS, FKS = 27, 525, 60


def _manifest() -> dict:
    if not dt.MANIFEST.exists():
        pytest.skip("sem manifest; rode `make dbt-build`")
    return json.loads(dt.MANIFEST.read_text(encoding="utf-8"))


def _testes(manifest: dict, nome: str) -> list[dict]:
    return [t for t in manifest["nodes"].values()
            if t["resource_type"] == "test" and (t.get("test_metadata") or {}).get("name") == nome]


#: A regra da macro, no código que o pacote de metadados também usa (F34): uma só.
declared_fks = dt.declared_foreign_keys
declared_pks = dt.declared_primary_keys


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


#: Toda PK e FK de `analytics`: a tabela, as colunas, o schema e a tabela apontada, as colunas apontadas.
_CHAVES_SQL = """
    select k.contype, r.relname,
           (select array_agg(a.attname order by x.ord) from unnest(k.conkey) with ordinality x(num, ord)
              join pg_attribute a on a.attrelid = k.conrelid and a.attnum = x.num),
           coalesce(pn.nspname, ''), coalesce(p.relname, ''),
           (select array_agg(b.attname order by y.ord) from unnest(k.confkey) with ordinality y(num, ord)
              join pg_attribute b on b.attrelid = k.confrelid and b.attnum = y.num),
           k.convalidated
    from pg_constraint k
    join pg_class r on r.oid = k.conrelid
    left join pg_class p on p.oid = k.confrelid
    left join pg_namespace pn on pn.oid = p.relnamespace
    where k.connamespace = 'analytics'::regnamespace and k.contype in ('p', 'f')
"""


def _desvios_das_chaves(linhas, manifest: dict) -> list[str]:
    """O que o armazém tem de diferente do declarado: por lista ordenada, não por conjunto — a FK duplicada
    conta —, e com o schema da tabela apontada (RVB6I-1-03)."""
    desvios = [f"não validada: {tuple(l)}" for l in linhas if not l[6]]
    pks = sorted((l[1], tuple(l[2])) for l in linhas if l[0] == "p")
    fks = sorted((l[1], tuple(l[2]), l[3], l[4], tuple(l[5])) for l in linhas if l[0] == "f")
    esperadas_pk = sorted((n, (c[0],)) for n, c in declared_pks(manifest).items())
    esperadas_fk = sorted((t, (c,), "analytics", p, (cp,)) for t, c, p, cp in declared_fks(manifest))
    if pks != esperadas_pk:
        desvios.append(f"PKs: a mais {[x for x in pks if x not in esperadas_pk]}, a menos {[x for x in esperadas_pk if x not in pks]}, repetidas {len(pks) - len(set(pks))}")
    if fks != esperadas_fk:
        desvios.append(f"FKs: a mais {[x for x in fks if x not in esperadas_fk]}, a menos {[x for x in esperadas_fk if x not in fks]}, repetidas {len(fks) - len(set(fks))}")
    return desvios


def test_a_guarda_das_chaves_aponta_a_duplicata_o_outro_schema_e_a_falta() -> None:
    """Contraprova da guarda do armazém, sem banco (RVB6I-1-03): partindo das linhas que o declarado daria, uma
    FK repetida, uma FK apontando para a tabela homônima de outro schema, uma FK a menos e uma não validada
    são apontadas; as linhas exatas, não."""
    manifest = _manifest()
    exatas = [("p", n, [c[0]], "", "", None, True) for n, c in declared_pks(manifest).items()]
    exatas += [("f", t, [c], "analytics", p, [cp], True) for t, c, p, cp in sorted(declared_fks(manifest))]
    assert _desvios_das_chaves(exatas, manifest) == []
    uma = next(l for l in exatas if l[0] == "f")
    assert _desvios_das_chaves(exatas + [uma], manifest) != []
    assert _desvios_das_chaves([l if l is not uma else (*l[:3], "outro_schema", *l[4:]) for l in exatas], manifest) != []
    assert _desvios_das_chaves([l for l in exatas if l is not uma], manifest) != []
    assert _desvios_das_chaves([l if l is not uma else (*l[:6], False) for l in exatas], manifest) != []


def test_o_pacote_traz_as_chaves_que_a_macro_instala() -> None:
    """F34: as PKs e FKs de `relations` são as da regra que as instala, e nenhuma relação fora de `analytics` traz
    chave. O armazém é conferido contra a mesma regra abaixo: o pacote e o banco saem da mesma declaração."""
    from mvp_ed1.models import pacote
    manifest = _manifest()
    gerado = json.loads(pacote.PACOTE.read_text(encoding="utf-8"))["relations"]
    pks = {r.split(".", 1)[1]: v["primary_key"] for r, v in gerado.items() if v["primary_key"]}
    fks = {(r.split(".", 1)[1], f["column"], f["references_relation"].split(".", 1)[1], f["references_column"])
           for r, v in gerado.items() for f in v["foreign_keys"]}
    assert pks == declared_pks(manifest) and len(pks) == MODELOS
    assert fks == declared_fks(manifest) and len(fks) == FKS
    assert [r for r, v in gerado.items() if (v["primary_key"] or v["foreign_keys"]) and not r.startswith("analytics.")] == []
    assert {f["references_relation"].split(".")[0] for v in gerado.values() for f in v["foreign_keys"]} == {"analytics"}


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
        linhas = c.execute(text(_CHAVES_SQL)).all()
    assert _desvios_das_chaves(linhas, manifest) == []


@pytest.mark.integracao
def test_o_tipo_que_cada_modelo_calcula_e_o_declarado(engine) -> None:
    """O que o contrato não compara (precisão, escala, comprimento): o SQL compilado num `select` sem linhas,
    lido do cursor com o `typmod` — nunca do catálogo da tabela, que já mostra o tipo depois da coerção."""
    manifest = _manifest()
    with dt._conectar() as conexao:
        calculado = dt.computed_types(conexao, manifest)
    assert dt.type_drift(calculado, manifest) == []
