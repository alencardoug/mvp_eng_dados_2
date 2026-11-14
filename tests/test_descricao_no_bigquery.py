"""Nenhuma coluna chega ao BigQuery com a descrição cortada (F4 dos Achados do nl_sql).

O BigQuery recusa a descrição de coluna com mais de 1.024 caracteres. A macro
`bigquery__alter_column_comment` manda a **versão curta**: o texto inteiro sem o
marcador, se couber; senão, a parte antes de `<!-- bigquery: fim do texto curto -->`,
que o glossário põe no fim da parte já completa. Sem marcador, ela corta e avisa — e
é esse corte que este teste proíbe.

A macro só roda no BigQuery, que não está de pé (Q14); o `make check` não a alcança
por um *build*. A prova é a **própria macro**, renderizada aqui com o ambiente Jinja do
dbt (`dbt_common`) e um adaptador que só registra o que receberia em `update_columns`:
o texto que estes testes medem é o que a macro publicaria, não uma cópia da regra
(RVB3-1-04). O que fica de fora é o adaptador do BigQuery e a chamada à API — limite
aceito, o mesmo da Q14.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from dbt_common.clients.jinja import MacroReturn, get_environment

RAIZ = pathlib.Path(__file__).resolve().parents[1]
MACRO = RAIZ / "dbt" / "macros" / "descricao_no_bigquery.sql"
MANIFEST = RAIZ / "dbt" / "target" / "manifest.json"
MARCA = "<!-- bigquery: fim do texto curto -->"
LIMITE = 1024
AVISO = " […] texto completo no catálogo (dbt docs)."


class _Relacao:
    def __init__(self, tipo: str) -> None:
        self.type = tipo


class _Adaptador:
    """No lugar do adaptador do BigQuery: guarda as colunas que a macro mandaria gravar."""

    def __init__(self) -> None:
        self.colunas: dict[str, dict] = {}

    def update_columns(self, relation: _Relacao, colunas: dict[str, dict]) -> None:
        self.colunas.update(colunas)


def _macros(fonte: str, tags: str = "{}") -> tuple[dict, _Adaptador]:
    """As macros do arquivo, chamáveis como o dbt as chama: `return` levanta `MacroReturn`."""
    def _return(valor):
        raise MacroReturn(valor)

    modulo: dict = {}

    def macro(nome: str):
        def chamar(*args, **kwargs):
            try:
                return getattr(modulo["m"], f"dbt_macro__{nome}")(*args, **kwargs)
            except MacroReturn as retorno:
                return retorno.value
        return chamar

    adaptador = _Adaptador()
    nomes = ("bigquery__alter_column_comment", "mvp_policy_tags", "texto_no_bigquery")
    contexto = {"return": _return, "adapter": adaptador, "fromjson": json.loads, "exceptions": None,
                "env_var": lambda nome, padrao=None: tags if nome == "MVP_POLICY_TAGS" else padrao,
                **{nome: macro(nome) for nome in nomes}}
    modulo["m"] = get_environment().from_string(fonte).make_module(vars=contexto)
    return {nome: contexto[nome] for nome in nomes}, adaptador


def publicado(descricoes: dict[str, str], fonte: str | None = None) -> dict[str, str]:
    """`coluna → texto` que `bigquery__alter_column_comment` mandaria ao BigQuery."""
    macros, adaptador = _macros(MACRO.read_text(encoding="utf-8") if fonte is None else fonte)
    macros["bigquery__alter_column_comment"](_Relacao("table"),
                                             {n: {"name": n, "description": d} for n, d in descricoes.items()})
    return {n: c["description"] for n, c in adaptador.colunas.items()}


def _colunas() -> dict[str, str]:
    if not MANIFEST.exists():
        pytest.skip("sem dbt/target/manifest.json; rode `make dbt-build`")
    nos = json.loads(MANIFEST.read_text(encoding="utf-8"))["nodes"]
    return {
        f"{no['schema']}.{no['name']}.{nome}": coluna.get("description") or ""
        for no in nos.values()
        if no["resource_type"] in ("model", "snapshot", "seed")
        for nome, coluna in no["columns"].items()
    }


def test_nenhuma_coluna_e_cortada_no_bigquery() -> None:
    colunas = _colunas()
    textos = publicado(colunas)
    assert textos.keys() == colunas.keys()
    problemas = [(c, len(t)) for c, t in textos.items() if len(t) > LIMITE or t.endswith(AVISO) or MARCA in t]
    assert problemas == [], problemas


def test_a_versao_curta_da_receita_leva_a_regra_do_pedido_realizado() -> None:
    """O F5 tem de chegar ao texto curto, e não só ao longo (plano, Bloco 3)."""
    coluna = "analytics.fact_sales_order_item.net_revenue_amount"
    texto = publicado({coluna: _colunas()[coluna]})[coluna]
    assert "Só pedido realizado conta" in texto
    assert MARCA not in texto


@pytest.mark.parametrize(
    ("coluna", "trechos"),
    [
        # RVB3-1-03: as regras que mudam o número estão antes do marcador.
        pytest.param("consumption.repeat_purchase_rate_after_support.repeat_purchase_rate",
                     ("pedido seguinte", "dos dois lados", "Janela aberta"), id="recompra"),
        pytest.param("consumption.order_to_delivery_time_by_region.avg_order_to_delivery_days",
                     ("remessa que fechou o ciclo", "ciclo fechado"), id="ciclo"),
        pytest.param("consumption.on_time_delivery_rate_by_carrier.on_time_rate",
                     ("livro de eventos", "Devolvida conta", "extraviada nunca entra"), id="pontualidade"),
    ],
)
def test_a_versao_curta_leva_as_regras_que_mudam_o_numero(coluna: str, trechos: tuple[str, ...]) -> None:
    descricao = _colunas()[coluna]
    assert MARCA in descricao, "o teste perdeu o objeto: a descrição não tem mais a versão curta"
    texto = publicado({coluna: descricao})[coluna]
    assert len(texto) < len(descricao.replace(MARCA, ""))             # é mesmo a parte curta
    for trecho in trechos:
        assert trecho in texto, (coluna, trecho)


@pytest.mark.parametrize(
    ("descricao", "esperado"),
    [
        pytest.param("a" * 1024, "a" * 1024, id="cabe-inteiro"),
        pytest.param("a" * 1025, "a" * (LIMITE - len(AVISO)) + AVISO, id="longo-sem-marca-e-cortado-com-aviso"),
        pytest.param("a" * 500 + MARCA + "b" * 600, "a" * 500, id="longo-com-marca-vai-a-parte-curta"),
        pytest.param("a" * 100 + MARCA + "b" * 100, "a" * 100 + "b" * 100, id="curto-com-marca-vai-inteiro-sem-ela"),
    ],
)
def test_a_regra_da_versao_curta(descricao: str, esperado: str) -> None:
    assert publicado({"c": descricao})["c"] == esperado


def test_a_marca_depois_do_limite_nao_salva() -> None:
    """Contraprova: com a parte curta maior que o limite, o texto passa do limite e o teste acusaria."""
    assert len(publicado({"c": "a" * 1100 + MARCA + "b"})["c"]) > LIMITE


@pytest.mark.parametrize(
    ("trecho", "mutante"),
    [
        pytest.param("{{ return((descricao.split(marca)[0]) | trim) }}", "{{ return(descricao) }}", id="devolve-o-longo"),
        pytest.param("{%- set limite = 1024 -%}", "{%- set limite = 2048 -%}", id="limite-errado"),
        pytest.param("{%- if inteiro | length <= limite -%}", "{%- if true -%}", id="nunca-encurta"),
        pytest.param("descricao[:limite - aviso | length] ~ aviso", "descricao", id="nao-corta"),
    ],
)
def test_a_guarda_pega_a_macro_mutante(trecho: str, mutante: str) -> None:
    """RVB3-1-04: a macro alterada **só em memória** faz algum caso falhar — a guarda vê a macro, não uma cópia."""
    fonte = MACRO.read_text(encoding="utf-8")
    assert fonte.count(trecho) == 1, trecho
    casos = {"curto": "a" * 500 + MARCA + "b" * 600, "sem_marca": "a" * 1025}
    esperado = {"curto": "a" * 500, "sem_marca": "a" * (LIMITE - len(AVISO)) + AVISO}
    assert publicado(casos) == esperado                                   # a macro de verdade
    assert publicado(casos, fonte.replace(trecho, mutante)) != esperado   # a mutante não passa


def test_a_policy_tag_so_em_tabela_e_pelo_mapa() -> None:
    """O mesmo caminho grava a *policy tag* derivada de `meta.sensitivity` (D71, D79)."""
    macros, adaptador = _macros(MACRO.read_text(encoding="utf-8"), tags='{"confidential": "tag/conf"}')
    coluna = {"c": {"name": "c", "description": "x", "meta": {"sensitivity": "confidential"}},
              "d": {"name": "d", "description": "y", "meta": {"sensitivity": "public"}}}
    macros["bigquery__alter_column_comment"](_Relacao("table"), coluna)
    assert {n: c["policy_tags"] for n, c in adaptador.colunas.items()} == {"c": ["tag/conf"], "d": []}
    macros["bigquery__alter_column_comment"](_Relacao("view"), coluna)
    assert adaptador.colunas["c"]["policy_tags"] == []
