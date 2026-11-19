"""As amostras de registros para o portal `gdados` (D95, ADR-0058 e as três retificações dele).

Até cinco linhas de cada relação do pacote de metadados da mesma publicação, com todas as colunas, em
`docs/amostras_de_registros.json`, ao lado do pacote. O arquivo é **do *build* que ele cita**: exportado
uma vez por publicação, com a procedência `verified`, e conferido na mesma invocação (`--conferir`). Depois
de outro *build* ou de uma restauração ele pode divergir do armazém, e a publicação seguinte o refaz.

**A máscara.** Todo valor de coluna `personal` vira o marcador `MARCADOR`; o nulo continua nulo. Nos
recipientes JSON do legado (`RECIPIENTES`) a estrutura fica, e só as folhas `personal` da relação de origem
viram marcador: a origem é a dependência do modelo (`stg_legacy__<t>` → `raw_legacy.<t>`) ou a coluna
`source_table` da linha. Origem ou forma não resolvida vira marcador inteiro. Em `findings`, o
`original_value` e o `cleaned_value` de coluna `personal` (ou desconhecida) viram marcador.

**O que não se mascara, por decisão do Owner (19/11/2026):** o conteúdo que um defeito do legado
(`TEXT_DELIMITER`) desloca para uma coluna não pessoal aparece como está, para mostrar o defeito.

**A ordem.** Pela chave declarada: a `primary_key` do pacote; senão o `grain` e a `identity` de
`view_rules`; senão o teste de unicidade da relação (coluna ou combinação, lidos do *manifest*); senão
todas as colunas, na ordem declarada, no tipo nativo (JSON pelo texto). Nas relações da lista fechada
(`prioridade`), as linhas com defeito registrado vêm antes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

from mvp_ed1.models import sensitivity

ROOT = sensitivity.ROOT
ARQUIVO = ROOT / "docs" / "amostras_de_registros.json"
PACOTE = ROOT / "docs" / "pacote_de_metadados.json"
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
FORMATO = 1
LINHAS = 5
MARCADOR = "<personal>"
#: O ambiente da exportação local; a fase GCP teria o seu.
AMBIENTE = "local"
#: Os recipientes JSON que levam a linha do legado, inteira ou em coleção (`legacy/classification.py`).
RECIPIENTES = ("original_payload", "cleaned_payload", "payloads", "last_payload", "findings")
_DEFEITO_NA_CLASSIFICACAO = "(c.classification <> 'accepted' or jsonb_array_length(coalesce(c.findings, '[]'::jsonb)) > 0)"


class ExportacaoRecusada(RuntimeError):
    """A exportação não roda: procedência não verificada, ou relação do pacote fora do armazém."""


# ── Declaração: o pacote e o manifest ───────────────────────────────────────


def carregar_pacote(caminho: Path = PACOTE) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def unicidades(manifest: dict) -> dict[str, list[list[str]]]:
    """`schema.relação` → as listas de colunas dos testes de unicidade declarados (coluna ou combinação)."""
    nome = {}
    for uid, no in {**manifest.get("nodes", {}), **manifest.get("sources", {})}.items():
        if no.get("resource_type") in ("model", "snapshot", "seed", "source"):
            nome[uid] = f"{no['schema']}.{no.get('identifier') or no.get('alias') or no['name']}"
    saida: dict[str, list[list[str]]] = {}
    for no in manifest.get("nodes", {}).values():
        meta = no.get("test_metadata") or {}
        kwargs = meta.get("kwargs") or {}
        if meta.get("name") == "unique" and kwargs.get("column_name"):
            colunas = [kwargs["column_name"]]
        elif meta.get("name") == "unique_combination_of_columns" and kwargs.get("combination_of_columns"):
            colunas = list(kwargs["combination_of_columns"])
        else:
            continue
        alvo = no.get("attached_node") or next(iter(no.get("depends_on", {}).get("nodes", [])), None)
        if alvo in nome:
            saida.setdefault(nome[alvo], []).append(colunas)
    return saida


def chave(relacao: str, pacote: dict, unicas: dict[str, list[list[str]]], colunas: list[str]) -> list[str]:
    """A ordem declarada da relação; todas as colunas na falta de chave."""
    r = pacote["relations"][relacao]
    if r.get("primary_key"):
        return list(r["primary_key"])
    regra = pacote.get("view_rules", {}).get(relacao)
    if regra:
        papeis = [c for c, v in regra["columns"].items() if v.get("role") in ("grain", "identity")]
        if papeis:
            return [c for c in colunas if c in papeis]
    candidatas = sorted(unicas.get(relacao, []), key=lambda cs: (len(cs), cs))
    if candidatas:
        return candidatas[0]
    return list(colunas)


def prioridade(relacao: str) -> str | None:
    """A expressão de defeito-primeiro da lista fechada (segunda e terceira retificações), sobre o alias `t`.

    0 vem antes de 1, e 1 antes de 2. Fora da lista, `None`: vale só a chave.
    """
    schema, nome = relacao.split(".", 1)
    if schema == "raw_legacy":
        captura = "(t._airbyte_meta->>'sync_id')::bigint"
        selecionada = "(select snapshot_id from staging.legacy_selected_capture)"
        return (f"case when {captura} = {selecionada} and exists (select 1 from trusted.legacy_classifications c "
                f"where c.source_table = '{nome}' and c.snapshot_id = {captura} and c.legacy_row_id = t.legacy_row_id "
                f"and {_DEFEITO_NA_CLASSIFICACAO}) then 0 when {captura} = {selecionada} then 1 else 2 end")
    if schema == "staging" and nome.startswith("stg_legacy__"):
        tabela = nome.removeprefix("stg_legacy__")
        return (f"case when coalesce(t.achados, '{{}}'::jsonb) <> '{{}}'::jsonb or exists (select 1 from "
                f"trusted.legacy_classifications c where c.source_table = '{tabela}' and c.snapshot_id = t.snapshot_id "
                f"and c.legacy_row_id = t.legacy_row_id and {_DEFEITO_NA_CLASSIFICACAO}) then 0 else 1 end")
    if relacao == "trusted.legacy_records":
        return "case when coalesce(t.value_findings, '{}'::jsonb) <> '{}'::jsonb then 0 else 1 end"
    if relacao in ("trusted.legacy_classifications", "trusted.legacy_eligible_records"):
        return ("case when t.classification <> 'accepted' or jsonb_array_length(coalesce(t.findings, '[]'::jsonb)) > 0 "
                "then 0 else 1 end")
    return None


# ── A máscara ────────────────────────────────────────────────────────────────


def pessoais(pacote: dict, relacao: str) -> set[str] | None:
    """As colunas `personal` de uma relação do pacote; `None` se a relação não existe nele."""
    r = pacote["relations"].get(relacao)
    if r is None:
        return None
    return {c for c, m in r["columns"].items() if m.get("sensitivity") == "personal"}


def origem(relacao: str, linha: dict[str, Any]) -> str | None:
    """A relação bruta de onde a linha do legado veio, ou `None` se não se resolve."""
    schema, nome = relacao.split(".", 1)
    if schema == "staging" and nome.startswith("stg_legacy__"):
        return "raw_legacy." + nome.removeprefix("stg_legacy__")
    tabela = linha.get("source_table")
    if isinstance(tabela, str) and tabela:
        return "raw_legacy." + tabela
    return None


def _linha_mascarada(objeto: Any, colunas_da_origem: set[str], pessoais_da_origem: set[str]) -> Any:
    if not isinstance(objeto, dict):
        return MARCADOR
    saida = {}
    for k, v in objeto.items():
        if v is None:
            saida[k] = None
        elif k in pessoais_da_origem or k not in colunas_da_origem:
            # Chave desconhecida é forma não resolvida: o conservador é mascarar.
            saida[k] = MARCADOR
        else:
            saida[k] = v
    return saida


def mascarar_recipiente(coluna: str, valor: Any, relacao: str, linha: dict, pacote: dict) -> Any:
    """Máscara por folha num recipiente JSON pessoal do legado; marcador inteiro se não resolver."""
    if valor is None:
        return None
    fonte = origem(relacao, linha)
    pess = pessoais(pacote, fonte) if fonte else None
    if pess is None:
        return MARCADOR
    todas = set(pacote["relations"][fonte]["columns"])
    if coluna in ("original_payload", "cleaned_payload"):
        return _linha_mascarada(valor, todas, pess)
    # `payloads` e `last_payload` são coleções de linhas (`legacy_presence_by_capture`,
    # `legacy_removed_records`): linha a linha, como manda a primeira retificação do ADR-0058.
    if coluna in ("payloads", "last_payload"):
        if not isinstance(valor, list):
            return MARCADOR
        return [_linha_mascarada(v, todas, pess) for v in valor]
    if coluna == "findings":
        if not isinstance(valor, list):
            return MARCADOR
        saida = []
        for achado in valor:
            if not isinstance(achado, dict):
                saida.append(MARCADOR)
                continue
            achado = dict(achado)
            alvo = achado.get("column")
            if alvo in pess or alvo not in todas:
                for campo in ("original_value", "cleaned_value"):
                    if achado.get(campo) is not None:
                        achado[campo] = MARCADOR
            saida.append(achado)
        return saida
    return MARCADOR


def mascarar(relacao: str, colunas: list[str], linha: dict[str, Any], pacote: dict) -> list[Any]:
    pess = pessoais(pacote, relacao) or set()
    saida = []
    for c in colunas:
        v = linha[c]
        if v is None or c not in pess:
            saida.append(v)
        elif c in RECIPIENTES:
            saida.append(mascarar_recipiente(c, v, relacao, linha, pacote))
        else:
            saida.append(MARCADOR)
    return saida


# ── A exportação ─────────────────────────────────────────────────────────────


def serializavel(valor: Any) -> Any:
    if isinstance(valor, (dt.datetime, dt.date, dt.time)):
        return valor.isoformat()
    if isinstance(valor, decimal.Decimal):
        return str(valor)  # exato, sem `float`
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, (bytes, memoryview)):
        return bytes(valor).hex()
    if isinstance(valor, dict):
        return {k: serializavel(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializavel(v) for v in valor]
    return valor


def _colunas_do_armazem(conexao, relacao: str) -> dict[str, str]:
    from sqlalchemy import text

    schema, nome = relacao.split(".", 1)
    linhas = conexao.execute(text(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = :s and table_name = :t order by ordinal_position"), {"s": schema, "t": nome}).all()
    return {c: t for c, t in linhas}


def _ordem(colunas: list[str], tipos: dict[str, str]) -> list[str]:
    return [f't."{c}"::text' if tipos.get(c) in ("json", "jsonb") else f't."{c}"' for c in colunas]


def procedencia(conexao) -> dict:
    from sqlalchemy import text

    linha = conexao.execute(text(
        "select status, reason, invocation_id, built_from_commit, built_at, sequence "
        "from governance.warehouse_provenance")).mappings().first()
    if linha is None or linha["status"] != "verified":
        raise ExportacaoRecusada(f"procedência não verificada: {dict(linha) if linha else 'sem linha'}")
    return serializavel(dict(linha))


def exportar(conexao, pacote: dict, manifest: dict, instante: str, ambiente: str = AMBIENTE,
             as_of_date: str | None = None, mascara=None) -> dict:
    """Monta o arquivo inteiro numa transação só leitura já aberta por quem chama.

    `mascara` troca a função de máscara: o oráculo dos testes pede as linhas sem máscara, na mesma ordem,
    e calcula o esperado por conta própria.
    """
    mascara = mascara or mascarar
    from sqlalchemy import text

    unicas = unicidades(manifest)
    relacoes: dict[str, dict] = {}
    for relacao in sorted(pacote["relations"]):
        tipos = _colunas_do_armazem(conexao, relacao)
        declaradas = list(pacote["relations"][relacao]["columns"])
        if not tipos:
            raise ExportacaoRecusada(f"{relacao}: está no pacote e não no armazém")
        if set(declaradas) != set(tipos):
            raise ExportacaoRecusada(f"{relacao}: colunas do pacote e do armazém diferem "
                                     f"({sorted(set(declaradas) ^ set(tipos))})")
        ordem = chave(relacao, pacote, unicas, declaradas)
        expressao = prioridade(relacao)
        criterio = ([expressao] if expressao else []) + _ordem(ordem, tipos)
        lista = ", ".join(f't."{c}"' for c in declaradas)
        sql = f"select {lista} from {relacao} t order by {', '.join(criterio)} limit {LINHAS}"
        linhas = [dict(l) for l in conexao.execute(text(sql)).mappings()]
        total = conexao.execute(text(f"select count(*) from {relacao}")).scalar_one()
        relacoes[relacao] = {
            "row_count": int(total),
            "order": {"defect_first": expressao is not None, "key": ordem},
            "columns": declaradas,
            "masked_columns": sorted(pessoais(pacote, relacao) or []),
            "rows": [serializavel(mascara(relacao, declaradas, l, pacote)) for l in linhas],
        }
    return {
        "format": FORMATO,
        "exported_at": instante,
        "provenance": procedencia(conexao),
        "environment": ambiente,
        "as_of_date": as_of_date,
        "masking": {"marker": MARCADOR, "rule": "ADR-0058", "personal_columns": "every `personal` column; "
                    "in legacy JSON payloads, the `personal` leaves of the source relation"},
        "relations": relacoes,
    }


def _as_of_date() -> str | None:
    import yaml

    projeto = yaml.safe_load((ROOT / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))
    valor = (projeto.get("vars") or {}).get("as_of_date")
    return str(valor) if valor is not None else None


def _em_transacao(fazer):
    from sqlalchemy import create_engine, text

    from mvp_ed1.db import WAREHOUSE, database_url

    motor = create_engine(database_url(WAREHOUSE))
    try:
        with motor.connect() as conexao:
            conexao.execute(text("set transaction isolation level repeatable read read only"))
            return fazer(conexao)
    finally:
        motor.dispose()


def escrever(arquivo: Path = ARQUIVO) -> dict:
    pacote = carregar_pacote()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    instante = dt.datetime.now(dt.timezone.utc).isoformat()
    dados = _em_transacao(lambda c: exportar(c, pacote, manifest, instante, as_of_date=_as_of_date()))
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return dados


def conferir(arquivo: Path = ARQUIVO) -> list[str]:
    """Refaz a exportação em memória, na mesma invocação do cabeçalho, e compara tudo."""
    if not arquivo.exists():
        return [f"{arquivo} ausente"]
    publicado = json.loads(arquivo.read_text(encoding="utf-8"))
    pacote = carregar_pacote()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def refazer(conexao):
        atual = procedencia(conexao)
        if atual["invocation_id"] != publicado["provenance"]["invocation_id"]:
            raise ExportacaoRecusada(
                f"outra invocação no armazém ({atual['invocation_id']}) que a do arquivo "
                f"({publicado['provenance']['invocation_id']}): a amostra é do build que cita, e não se confere contra outro")
        # O instante é o da fotografia; ambiente e data vêm da declaração, e não do arquivo conferido
        # (RVPB1-1-03): ecoar os dois do arquivo aceitaria qualquer adulteração deles.
        return exportar(conexao, pacote, manifest, publicado["exported_at"], AMBIENTE, _as_of_date())

    refeito = json.loads(json.dumps(_em_transacao(refazer), ensure_ascii=False))
    if refeito == publicado:
        return []
    problemas = [f"{k}: difere" for k in publicado if k != "relations" and publicado.get(k) != refeito.get(k)]
    for r in sorted(set(publicado.get("relations", {})) | set(refeito["relations"])):
        if publicado.get("relations", {}).get(r) != refeito["relations"].get(r):
            problemas.append(f"{r}: difere")
    return problemas


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--conferir", action="store_true", help="compara o arquivo com a exportação refeita, na mesma invocação")
    args = p.parse_args(list(argv) if argv is not None else None)
    if args.conferir:
        problemas = conferir()
        for linha in problemas[:20]:
            print(linha, file=sys.stderr)
        print("amostras: em dia com a invocação que citam" if not problemas else f"amostras: {len(problemas)} diferença(s)")
        return 1 if problemas else 0
    dados = escrever()
    print(f"amostras escritas: {len(dados['relations'])} relações, invocação {dados['provenance']['invocation_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
