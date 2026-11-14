"""Nenhuma coluna chega ao BigQuery com a descrição cortada (F4 dos Achados do nl_sql).

O BigQuery recusa a descrição de coluna com mais de 1.024 caracteres. A macro
`bigquery__alter_column_comment` manda a **versão curta**: o texto inteiro sem o
marcador, se couber; senão, a parte antes de `<!-- bigquery: fim do texto curto -->`,
que o glossário põe no fim da parte já completa. Sem marcador, ela corta e avisa — e
é esse corte que este teste proíbe.

A macro só roda no BigQuery, que não está de pé (Q14); o `make check` não a alcança.
A prova é a regra repetida aqui sobre o *manifest* local, com a mesma constante que
a macro usa, e as contraprovas sobre textos montados.
"""

from __future__ import annotations

import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
MACRO = RAIZ / "dbt" / "macros" / "descricao_no_bigquery.sql"
MANIFEST = RAIZ / "dbt" / "target" / "manifest.json"
MARCA = "<!-- bigquery: fim do texto curto -->"
LIMITE = 1024


def texto_no_bigquery(descricao: str) -> tuple[str, bool]:
    """(texto, cortado): a regra de `texto_no_bigquery` da macro."""
    inteiro = descricao.replace(MARCA, "")
    if len(inteiro) <= LIMITE:
        return inteiro, False
    if MARCA in descricao:
        return descricao.split(MARCA)[0].strip(), False
    return descricao[:LIMITE], True


def _colunas() -> list[tuple[str, str]]:
    if not MANIFEST.exists():
        pytest.skip("sem dbt/target/manifest.json; rode `make dbt-build`")
    nos = json.loads(MANIFEST.read_text(encoding="utf-8"))["nodes"]
    return [
        (f"{no['schema']}.{no['name']}.{nome}", coluna.get("description") or "")
        for no in nos.values()
        if no["resource_type"] in ("model", "snapshot", "seed")
        for nome, coluna in no["columns"].items()
    ]


def test_a_macro_usa_a_mesma_marca_e_o_mesmo_limite() -> None:
    texto = MACRO.read_text(encoding="utf-8")
    assert f"'{MARCA}'" in texto
    assert "{%- set limite = 1024 -%}" in texto
    assert "texto_no_bigquery(copia.get('description')" in texto


def test_nenhuma_coluna_e_cortada_no_bigquery() -> None:
    problemas = []
    for coluna, descricao in _colunas():
        texto, cortado = texto_no_bigquery(descricao)
        if cortado or len(texto) > LIMITE:
            problemas.append((coluna, len(descricao)))
    assert problemas == [], problemas


def test_a_versao_curta_da_receita_leva_a_regra_do_pedido_realizado() -> None:
    """O F5 tem de chegar ao texto curto, e não só ao longo (plano, Bloco 3)."""
    descricao = dict(_colunas())["analytics.fact_sales_order_item.net_revenue_amount"]
    texto, _ = texto_no_bigquery(descricao)
    assert "Só pedido realizado conta" in texto
    assert MARCA not in texto


@pytest.mark.parametrize(
    ("descricao", "cortado", "tamanho_maximo"),
    [
        pytest.param("a" * 1024, False, 1024, id="cabe-inteiro"),
        pytest.param("a" * 1025, True, 1024, id="longo-sem-marca-e-cortado"),
        pytest.param("a" * 500 + MARCA + "b" * 600, False, 500, id="longo-com-marca-vai-a-parte-curta"),
        pytest.param("a" * 100 + MARCA + "b" * 100, False, 200, id="curto-com-marca-vai-inteiro-sem-ela"),
    ],
)
def test_a_regra_da_versao_curta(descricao: str, cortado: bool, tamanho_maximo: int) -> None:
    texto, foi_cortado = texto_no_bigquery(descricao)
    assert foi_cortado is cortado
    assert len(texto) <= tamanho_maximo
    assert MARCA not in texto


def test_a_marca_depois_do_limite_nao_salva() -> None:
    """Contraprova: com a parte curta maior que o limite, o texto passa do limite e o teste acusaria."""
    texto, _ = texto_no_bigquery("a" * 1100 + MARCA + "b")
    assert len(texto) > LIMITE
