"""O tipo declarado e a chave primária das colunas de `analytics` (Bloco 6, ADR-0056; Q35).

── O que é declaração e o que é derivado ───────────────────────────────────────
O `data_type` e a PK de cada coluna de `analytics` são **declaração**, no `.yml` escrito à mão. Este
módulo os **escreveu uma vez** (`escrever`), a partir do tipo que cada modelo calcula hoje — e só
preenche o que falta: o `data_type` que já está no `.yml` é a declaração, e diferente do calculado é
achado da guarda, nunca reescrito aqui. Mudar um tipo é mudar o `.yml`.

O tipo calculado sai do **cursor**: o SQL compilado de cada modelo, num `select` sem linhas, e o
`typmod` que o protocolo devolve passado ao `format_type` (medido no Bloco 6: dá `numeric(12,4)`,
`character varying(20)`, `text`). Nunca do catálogo da tabela, que mostra o tipo depois da coerção: o
*contract* grava `numeric(12,6)` calculado numa coluna `numeric(12,4)` arredondando, calado, e o catálogo
diria `numeric(12,4)`. O `get_column_schema_from_query` do dbt descarta o `typmod`.

O nome que vai ao `.yml` é o do PostgreSQL, salvo onde o BigQuery pede outro — o `cast` da checagem do
contrato lá recusa `numeric(12,4)`, e `character varying` e `timestamp with time zone` não são nomes
dele. Nesses, a expressão em linha por alvo, a mesma do `consumption` (o `data_type` não chama macro do
projeto, medido). A escala no BigQuery continua a do SQL (`decimal_fixo`).

A **PK** é a chave substituta de cada modelo: a coluna com `unique`, terminada em `_key`, que não é chave
natural. Uma por modelo, ou o módulo recusa.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

from mvp_ed1.models import sensitivity, value_domains

ROOT = sensitivity.ROOT
ANALYTICS_YML = ROOT / "dbt" / "models" / "analytics" / "_analytics__models.yml"
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
SCHEMA = "analytics"

#: O nome no BigQuery quando o do PostgreSQL não serve lá; `None` = o mesmo nome.
_NO_BIGQUERY = (
    (re.compile(r"character varying(\(\d+\))?"), "string"),
    (re.compile(r"timestamp with time zone"), "timestamp"),
    (re.compile(r"numeric\(\d+,\d+\)"), "numeric"),
)


def yml_value(tipo: str) -> str:
    """O texto do `data_type` no `.yml` para o tipo do PostgreSQL: ele mesmo, ou a expressão por alvo."""
    for padrao, bigquery in _NO_BIGQUERY:
        if padrao.fullmatch(tipo):
            return "{{ '" + tipo + "' if target.type != 'bigquery' else '" + bigquery + "' }}"
    return tipo


def postgres_name(declarado: str) -> str:
    """O tipo do PostgreSQL que um `data_type` declarado diz — o lado `target.type != 'bigquery'`."""
    m = re.fullmatch(r"\{\{ '([^']+)' if target\.type != 'bigquery' else '[^']+' \}\}", declarado)
    return m.group(1) if m else declarado


def analytics_models(manifest: dict) -> dict[str, dict]:
    return {n["name"]: n for n in manifest["nodes"].values()
            if n["resource_type"] == "model" and n["schema"] == SCHEMA}


def computed_types(conexao, manifest: dict) -> dict[str, dict[str, str]]:
    """`modelo → coluna → tipo` calculado: o SQL compilado num `select` sem linhas, lido do cursor."""
    saida: dict[str, dict[str, str]] = {}
    for nome, no in sorted(analytics_models(manifest).items()):
        sql = no.get("compiled_code")
        if not sql:
            raise ValueError(f"`{nome}` sem SQL compilado no manifest; rode `make dbt-build`")
        cursor = conexao.execute(f"select * from ({sql}) as _calculado limit 0")
        colunas = {}
        for i, d in enumerate(cursor.description):
            colunas[d.name] = conexao.execute("select format_type(%s, %s)", (d.type_code, cursor.pgresult.fmod(i))).fetchone()[0]
        saida[nome] = colunas
    return saida


def primary_keys(manifest: dict) -> dict[str, str]:
    """`modelo → coluna` da PK: a única coluna com `unique`, terminada em `_key`, que não é chave natural."""
    modelos = analytics_models(manifest)
    unicas: dict[str, set[str]] = {n: set() for n in modelos}
    for t in manifest["nodes"].values():
        if t["resource_type"] != "test" or (t.get("test_metadata") or {}).get("name") != "unique":
            continue
        pai = manifest["nodes"].get(t.get("attached_node") or "", {})
        if pai.get("name") in modelos:
            unicas[pai["name"]].add(t["column_name"])
    saida, recusas = {}, []
    for nome, cols in sorted(unicas.items()):
        candidatas = sorted(c for c in cols if c.endswith("_key") and "natural" not in c)
        if len(candidatas) != 1:
            recusas.append(f"{nome}: {candidatas or 'nenhuma'}")
        else:
            saida[nome] = candidatas[0]
    if recusas:
        raise ValueError("PK ambígua ou ausente: " + "; ".join(recusas))
    return saida


def type_drift(calculado: dict[str, dict[str, str]], manifest: dict) -> list[str]:
    """O que o contrato não pega: a coluna cujo tipo calculado (com os modificadores) não é o declarado.

    O `data_type` do *manifest* é o renderizado para o alvo da análise; o lado do PostgreSQL sai de
    `postgres_name`, que também lê a expressão por alvo quando o *manifest* vem de outro alvo."""
    saida = []
    for nome, no in sorted(analytics_models(manifest).items()):
        declarados = {c: postgres_name(v.get("data_type") or "") for c, v in no["columns"].items()}
        for coluna, tipo in calculado.get(nome, {}).items():
            if declarados.get(coluna) != tipo:
                saida.append(f"{nome}.{coluna}: declarado {declarados.get(coluna)!r}, calculado {tipo!r}")
        for coluna in sorted(set(declarados) - set(calculado.get(nome, {}))):
            saida.append(f"{nome}.{coluna}: declarada e não calculada")
    return saida


def write(texto: str, tipos: dict[str, dict[str, str]], pks: dict[str, str]) -> tuple[str, list[str]]:
    """O `.yml` com o `data_type` e a PK que faltam; (texto, divergências do que já estava declarado)."""
    linhas = texto.split("\n")
    divergencias = []
    for modelo in sorted(tipos):
        for coluna, tipo in tipos[modelo].items():
            ini, fim, recuo = value_domains._item_da_coluna(linhas, modelo, coluna)
            filho = recuo + 2
            valor = yml_value(tipo)
            existente = next((i for i in range(ini + 1, fim)
                              if sensitivity._indent(linhas[i]) == filho and linhas[i].strip().startswith("data_type:")), None)
            novas = []
            if existente is not None:
                declarado = linhas[existente].split(":", 1)[1].strip()
                if declarado.startswith(("'", '"')):
                    declarado = json.loads(declarado) if declarado.startswith('"') else declarado[1:-1]
                if declarado != valor:
                    divergencias.append(f"{modelo}.{coluna}: declarado {declarado!r}, calculado {valor!r}")
            else:
                novas.append(" " * filho + "data_type: " + (json.dumps(valor) if "{" in valor else valor))
            tem_pk = any(sensitivity._indent(linhas[i]) == filho and linhas[i].strip() == "constraints:" for i in range(ini + 1, fim))
            if pks.get(modelo) == coluna and not tem_pk:
                novas += [" " * filho + "constraints:", " " * (filho + 2) + "- type: primary_key"]
            if novas:
                linhas[ini + 1:ini + 1] = novas
    return "\n".join(linhas), divergencias


def _conectar():
    import psycopg
    from sqlalchemy import create_engine
    from mvp_ed1.db import WAREHOUSE, database_url
    url = create_engine(database_url(WAREHOUSE)).url
    return psycopg.connect(host=url.host, port=url.port, user=url.username, password=url.password, dbname=url.database)


def main(argv: list[str]) -> int:
    if argv[:1] != ["escrever"]:
        print("uso: python -m mvp_ed1.models.data_types escrever", file=sys.stderr)
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with _conectar() as conexao:
        tipos = computed_types(conexao, manifest)
    texto, divergencias = write(ANALYTICS_YML.read_text(encoding="utf-8"), tipos, primary_keys(manifest))
    for d in divergencias:
        print("divergente:", d)
    if divergencias:
        return 1
    ANALYTICS_YML.write_text(texto, encoding="utf-8")
    print(f"escrito: {sum(len(c) for c in tipos.values())} colunas, {len(primary_keys(manifest))} PKs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
