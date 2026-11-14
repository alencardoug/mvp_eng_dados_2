"""O contrato do pacote de metadados (D91): o esquema é válido e o exemplo o cumpre.

O pacote ainda não é gerado (Bloco 4). Até lá, o que os consumidores leem é o
esquema e o exemplo de `docs/`, e é isso que se guarda aqui, sem banco nem
manifest: o esquema é JSON Schema 2020-12 válido, o exemplo passa nele, e cada
regra que a especificação promete — chave sempre presente, formato fixo, valor
fora da lista recusado, sem resultado distinto de sucesso — tem contraprova:
o exemplo alterado é recusado.
"""

from __future__ import annotations

import copy
import json
import pathlib

import jsonschema
import pytest

from mvp_ed1.models import lineage

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ESQUEMA = RAIZ / "docs/pacote_de_metadados.schema.json"
EXEMPLO = RAIZ / "docs/pacote_de_metadados.exemplo.json"
TESTE = "test.mvp_ed1.not_null_fact_sales_order_item_net_revenue_amount.744c563ed6"
VIEW = "consumption.average_order_value_by_channel_and_segment"
CHECK = "tests/test_acesso.py::test_o_declarado_e_a_politica_da_governanca"


def _carregar(caminho: pathlib.Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validador() -> jsonschema.Draft202012Validator:
    esquema = _carregar(ESQUEMA)
    jsonschema.Draft202012Validator.check_schema(esquema)
    return jsonschema.Draft202012Validator(esquema)


@pytest.fixture()
def exemplo() -> dict:
    return _carregar(EXEMPLO)


def test_o_exemplo_cumpre_o_esquema(validador, exemplo) -> None:
    erros = sorted(validador.iter_errors(exemplo), key=str)
    assert not erros, [e.message for e in erros]


def test_o_exemplo_esta_na_forma_deterministica(exemplo) -> None:
    """A forma que a especificação promete ao pacote: chaves em ordem, dois espaços, quebra no fim."""
    esperado = json.dumps(exemplo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert EXEMPLO.read_text(encoding="utf-8") == esperado


def test_a_linhagem_do_pacote_e_o_formato_do_exportador(validador) -> None:
    """O pacote leva o `lineage --json` sem alteração: o formato dele é o do módulo."""
    esquema = _carregar(ESQUEMA)
    assert esquema["$defs"]["lineage"]["properties"]["format"]["const"] == lineage.JSON_FORMAT


def test_uma_auditoria_completa_passa(validador, exemplo) -> None:
    """A condição do estado `audited` não recusa o caso legítimo: commit, os três critérios e a referência."""
    auditada = _com(
        exemplo,
        {
            "status": "audited",
            "commit": "abc1234",
            "criteria": ["non_additivity", "time_dependent_balance", "truncated_population"],
            "reference": "tests/referencia.py",
            "findings": [],
        },
        "view_audits",
        VIEW,
    )
    assert not list(validador.iter_errors(auditada))


def test_o_resultado_dos_testes_aponta_para_a_execucao_declarada(exemplo) -> None:
    """O que o esquema não liga entre seções: cada resultado é da execução do `run_results`, e a marca
    `same_invocation_as_manifest` diz a verdade. O gerador do Bloco 4 herda esta conferência."""
    dbt = exemplo["provenance"]["dbt"]
    mesma = dbt["run_results_invocation_id"] == dbt["manifest_invocation_id"]
    assert dbt["run_results_invocation_id"] and dbt["manifest_invocation_id"]
    for teste in exemplo["tests"].values():
        if teste["result"] is not None:
            assert teste["result"]["invocation_id"]
            assert teste["result"]["invocation_id"] == dbt["run_results_invocation_id"]
            assert teste["result"]["same_invocation_as_manifest"] is mesma


def test_as_concessoes_da_source_vem_do_meta(exemplo) -> None:
    """Na *source*, quem lê é o `meta.grants.select`, que a macro de acesso concede (RVF-1-01)."""
    for relacao in exemplo["relations"].values():
        if relacao["resource_type"] == "source":
            esperado = sorted(((relacao["meta"].get("grants") or {}).get("select")) or [])
            assert relacao["grants_select"] == esperado


def test_o_grao_e_o_da_convencao_da_descricao(exemplo) -> None:
    """`grain` é o texto entre `**Grão:` e `**` no início da descrição; sem a marca, `null`."""
    for relacao in exemplo["relations"].values():
        descricao = relacao["description"] or ""
        if descricao.startswith("**Grão:"):
            esperado = descricao[len("**Grão:"):].split("**", 1)[0].strip()
            assert relacao["grain"] == esperado
        else:
            assert relacao["grain"] is None


def test_toda_view_de_pergunta_tem_estado_de_auditoria(exemplo) -> None:
    """A view de cada pergunta aparece em `view_audits`, mesmo quando ainda `not_audited`."""
    views = {p["view"] for p in exemplo["questions"].values()}
    assert views and views <= set(exemplo["view_audits"])


# ── Contraprovas: cada regra recusa o que deve recusar ────────────────────────


def _sem(dado: dict, *caminho: str) -> dict:
    copia = copy.deepcopy(dado)
    alvo = copia
    for chave in caminho[:-1]:
        alvo = alvo[chave]
    del alvo[caminho[-1]]
    return copia


def _com(dado: dict, valor, *caminho: str) -> dict:
    copia = copy.deepcopy(dado)
    alvo = copia
    for chave in caminho[:-1]:
        alvo = alvo[chave]
    alvo[caminho[-1]] = valor
    return copia




@pytest.mark.parametrize(
    "alterar",
    [
        pytest.param(lambda e: _sem(e, "description_gaps"), id="secao-ausente"),
        pytest.param(lambda e: _sem(e, "relations", VIEW, "columns", "sales_channel_name", "description"), id="chave-omitida-em-vez-de-null"),
        pytest.param(lambda e: _com(e, 2, "format"), id="formato-desconhecido"),
        pytest.param(lambda e: _com(e, "secret", "relations", VIEW, "columns", "sales_channel_name", "sensitivity"), id="sensibilidade-fora-da-lista"),
        pytest.param(lambda e: _com(e, "success", "tests", TESTE, "result", "status"), id="estado-de-teste-fora-da-lista"),
        pytest.param(lambda e: _com(e, {}, "tests", TESTE, "result"), id="resultado-vazio-em-vez-de-null"),
        pytest.param(lambda e: _com(e, "verified_by_hand", "provenance", "warehouse", "status"), id="procedencia-fora-da-lista"),
        pytest.param(lambda e: _com(e, "x", "lineage", "relations", VIEW, "columns", "sales_channel_name", "origins", 0, "kind"), id="tipo-de-origem-fora-da-lista"),
        pytest.param(lambda e: _com(e, "abc", "provenance", "inputs_sha256"), id="hash-malformado"),
        pytest.param(lambda e: _com(e, 1, "campo_inventado"), id="chave-desconhecida-no-topo"),
        pytest.param(lambda e: _com(e, None, "tests", TESTE, "result", "executed_at"), id="sucesso-sem-data"),
        pytest.param(lambda e: _com(e, "audited", "view_audits", VIEW, "status"), id="auditada-sem-commit-criterios-referencia"),
        pytest.param(lambda e: _com(e, "abc1234", "view_audits", VIEW, "commit"), id="nao-auditada-com-commit"),
        pytest.param(lambda e: _com(e, "verified", "provenance", "warehouse", "status"), id="armazem-verificado-na-versao-1"),
        pytest.param(lambda e: _com(e, None, "provenance", "dbt", "run_results_invocation_id"), id="run-results-sem-procedencia"),
        pytest.param(lambda e: _sem(e, "provenance", "tree_dirty_at_generation"), id="sem-estado-da-arvore"),
        pytest.param(lambda e: _sem(e, "provenance", "environment"), id="sem-ambiente"),
        pytest.param(lambda e: _com(e, "", "provenance", "dbt", "run_results_invocation_id"), id="run-results-com-invocation-vazia"),
        pytest.param(lambda e: _com(e, "", "tests", TESTE, "result", "invocation_id"), id="resultado-com-invocation-vazia"),
        pytest.param(lambda e: _com(e, "", "relations", VIEW, "columns", "sales_channel_name", "description"), id="descricao-vazia-em-vez-de-null"),
        pytest.param(lambda e: _com(e, "", "relations", VIEW, "grain"), id="grao-vazio-em-vez-de-null"),
        pytest.param(lambda e: _com(e, ["analyst", "analyst"], "relations", VIEW, "grants_select"), id="papel-repetido"),
        pytest.param(lambda e: _sem(e, "checks"), id="sem-a-secao-do-pytest"),
        pytest.param(lambda e: _com(e, {"status": "ok", "executed_at": "2026-11-14T00:00:00Z", "run_id": "x"}, "checks", CHECK, "result"), id="estado-do-pytest-fora-da-lista"),
        pytest.param(lambda e: _com(e, {"status": "pass", "executed_at": None, "run_id": "x"}, "checks", CHECK, "result"), id="pytest-pass-sem-data"),
        pytest.param(lambda e: _com(e, {"status": "pass", "executed_at": "", "run_id": "x"}, "checks", CHECK, "result"), id="pytest-pass-com-data-vazia"),
        pytest.param(lambda e: _com(e, {"status": "pass", "executed_at": "", "invocation_id": "x", "same_invocation_as_manifest": False}, "tests", TESTE, "result"), id="dbt-pass-com-data-vazia"),
        pytest.param(lambda e: _com(e, "camada_inventada", "checks", CHECK, "layer"), id="camada-fora-da-lista"),
        pytest.param(lambda e: _sem(e, "checks", CHECK, "layer"), id="sem-camada"),
        pytest.param(lambda e: _com(e, "X1", "open_items", 0, "id"), id="item-aberto-com-id-invalido"),
        pytest.param(lambda e: _com(e, "README.md#x", "open_items", 0, "anchor"), id="ancora-fora-de-docs"),
        pytest.param(lambda e: _com(e, "closed", "open_items", 0, "state"), id="item-aberto-fechado"),
        pytest.param(
            lambda e: _com(
                e,
                {"status": "audited", "commit": "abc1234", "criteria": ["non_additivity", "time_dependent_balance", "truncated_population"], "reference": "", "findings": []},
                "view_audits",
                VIEW,
            ),
            id="auditada-com-referencia-vazia",
        ),
    ],
)
def test_o_esquema_recusa_o_exemplo_alterado(validador, exemplo, alterar) -> None:
    assert list(validador.iter_errors(alterar(exemplo)))
