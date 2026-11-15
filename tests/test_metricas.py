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


# ── A tabela das perguntas (Bloco 5, item 9; F23) ───────────────────────────────

def _manifest() -> dict:
    import json
    caminho = metrics.sensitivity.ROOT / "dbt" / "target" / "manifest.json"
    if not caminho.exists():
        pytest.skip("sem manifest; rode `make dbt-build`")
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_fatos_e_dimensoes_da_tabela_sao_os_que_a_view_le() -> None:
    """O oráculo é independente da declaração: o `depends_on` que o dbt compilou para cada view."""
    manifest = _manifest()
    nos = manifest["nodes"]
    for no in nos.values():
        if no["resource_type"] != "model" or no["schema"] != "consumption":
            continue
        lidas = {f"{nos[d]['schema']}.{nos[d]['name']}" for d in no["depends_on"]["nodes"] if d in nos}
        fatos, dims = metrics.relations(DOC, no["name"])
        assert set(fatos) | set(dims) == {r for r in lidas if r.startswith("analytics.")}, no["name"]


def test_a_aditividade_declarada_e_a_do_comeco_da_descricao() -> None:
    """A descrição da coluna de `consumption` que começa pela aditividade diz a mesma que a declaração (F28)."""
    import re
    import yaml
    rotulo = {"Aditiva": "additive", "Semiaditiva": "semi_additive", "Não aditiva": "non_additive"}
    texto = (metrics.sensitivity.ROOT / "dbt" / "models" / "consumption" / "_consumption__models.yml").read_text(encoding="utf-8")
    divergentes, conferidas = [], 0
    for modelo in yaml.safe_load(texto)["models"]:
        view = DOC["views"][modelo["name"]]
        for coluna in modelo.get("columns") or []:
            m = re.match(r"(Aditiva|Semiaditiva|Não aditiva)\b", (coluna.get("description") or "").strip())
            if not m or metrics.role(coluna["name"], view["columns"][coluna["name"]])[0] not in ("measure", "metric", "reference"):
                continue
            conferidas += 1
            if metrics.additivity(DOC, view, coluna["name"]) != rotulo[m.group(1)]:
                divergentes.append(f"{modelo['name']}.{coluna['name']}")
    assert divergentes == [] and conferidas > 60


def test_a_tabela_gerada_e_lida_pelo_pacote_com_os_nomes_fisicos() -> None:
    """O pacote lê a tabela gerada (`questions`): toda medida é coluna da view, e a aditividade é a declarada."""
    from mvp_ed1.models import pacote
    lidas = pacote._perguntas(metrics.sensitivity.ROOT.joinpath(
        "docs", "glossario_de_negocio", "perguntas_de_negocio.md").read_text(encoding="utf-8"))
    for pergunta, q in lidas.items():
        nome = q["view"].split(".", 1)[1]
        view = DOC["views"][nome]
        for medida in q["measures"]:
            assert medida["column"] in view["columns"], (pergunta, medida["column"])
            assert medida["additivity"] == metrics.additivity(DOC, view, medida["column"]), (pergunta, medida["column"])


# ── O que o pacote publica (Bloco 5, item 10) ───────────────────────────────────

def test_o_pacote_publica_toda_medida_metrica_e_filtro_da_declaracao() -> None:
    """`metrics` e `filters` são a declaração inteira: nenhuma medida, métrica ou filtro fica de fora, e todo
    nome citado (filtro da medida, parte da métrica) está publicado."""
    publicadas, filtros = metrics.package_fields(DOC)
    assert set(publicadas) == set(DOC["measures"]) | set(DOC["metrics"])
    assert set(filtros) == set(DOC["filters"])
    for nome, m in publicadas.items():
        assert set(m["filters"] or []) <= set(filtros), nome
        assert {m[k] for k in ("numerator", "denominator", "minuend", "subtrahend") if m[k]} <= set(publicadas), nome
        assert (m["source"] is None) == (m["kind"] != "measure"), nome
    for f in filtros.values():
        assert (metrics.sensitivity.ROOT / "docs" / f["concept"]).is_file(), f["concept"]


def test_as_colunas_publicadas_casam_com_as_medidas_das_perguntas() -> None:
    """O oráculo é o `questions` do pacote, lido da tabela gerada: cada medida da pergunta montada é coluna de
    exatamente uma medida ou métrica, com a mesma aditividade; e nenhuma coluna publicada sobra."""
    from mvp_ed1.models import pacote
    publicadas, _ = metrics.package_fields(DOC)
    por_coluna: dict[str, list[str]] = {}
    for nome, m in publicadas.items():
        for c in m["columns"]:
            por_coluna.setdefault(c["column"], []).append(c["additivity"])
    lidas = pacote._perguntas(metrics.sensitivity.ROOT.joinpath(
        "docs", "glossario_de_negocio", "perguntas_de_negocio.md").read_text(encoding="utf-8"))
    esperadas = {}
    for q in lidas.values():
        if "reference" in DOC["views"][q["view"].split(".", 1)[1]]:
            continue
        for medida in q["measures"]:
            esperadas[f"{q['view']}.{medida['column']}"] = [medida["additivity"]]
    assert por_coluna == esperadas
