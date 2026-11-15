"""O catálogo das métricas e o montador, sem banco (Bloco 5, Parte B; ADR-0055).

O que o banco não precisa dizer: o catálogo versionado carrega estrito, cada referência entre as seções
existe, e o montador é determinístico e só usa o que a declaração diz.
"""

from __future__ import annotations

import copy

import pytest

from mvp_ed1.models import metrics

DOC = metrics.load_catalog()


def test_o_catalogo_versionado_carrega_e_cobre_as_16_views() -> None:
    assert len(DOC["views"]) == 16
    assert {v["question"] for v in DOC["views"].values()} == {f"P{n:02d}" for n in range(1, 17)}


def test_a_montagem_e_deterministica_e_so_junta_o_que_a_view_usa() -> None:
    sql = metrics.assemble(DOC, "cart_conversion_rate_by_channel")
    assert sql == metrics.assemble(copy.deepcopy(DOC), "cart_conversion_rate_by_channel")
    assert "d.date_key = f.cart_created_date_key" in sql
    vendas = metrics.assemble(DOC, "average_order_value_by_channel_and_segment")
    assert "dim_customer" in vendas and "dim_geography" not in vendas and "dim_category" not in vendas
    margem = metrics.assemble(DOC, "gross_margin_by_category")
    assert "full outer join" in margem and "dim_product" in margem      # a categoria do custo depende do produto


def test_a_view_por_referencia_nao_se_monta() -> None:
    with pytest.raises(ValueError, match="por referência"):
        metrics.assemble(DOC, "top_skus_by_revenue")


@pytest.mark.parametrize("trecho, erro", [
    ("combine: {type: full, keys:", "booleano"),
])
def test_on_no_yaml_e_recusado(tmp_path, trecho, erro) -> None:
    texto = metrics.CATALOG.read_text(encoding="utf-8").replace(trecho, trecho.replace("keys:", "on:"), 1)
    with pytest.raises(ValueError, match=erro):
        metrics.load_catalog(tmp_path / "m.yml", texto)


def test_referencias_quebradas_sao_recusadas(tmp_path) -> None:
    texto = metrics.CATALOG.read_text(encoding="utf-8")
    casos = [
        ("    filters: [realised_order]\n    additivity: non_additive", "    filters: [sale_dispatch]\n    additivity: non_additive", "não é da fonte"),
        ("    numerator: converted_cart_count", "    numerator: nao_existe", "não é medida nem métrica"),
        ("      cart_count: measure", "      cart_count: medida", "papel"),
    ]
    for de, para, erro in casos:
        assert texto.count(de) >= 1, de
        with pytest.raises(ValueError, match=erro):
            metrics.load_catalog(tmp_path / "m.yml", texto.replace(de, para, 1))
