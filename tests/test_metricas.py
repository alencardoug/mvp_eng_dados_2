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
        ("  ticket_medio.md: [average_order_value]", "  ticket_medio.md: [ticket_medio]", "não é medida nem métrica"),
        ("  ticket_medio.md: [average_order_value]", "  ticket_inventado.md: [average_order_value]", "não existe no glossário"),
        ("  ticket_medio.md: [average_order_value]", "  ticket_medio.md: []", "sem medidas"),
        ("  average_order_value_by_channel_and_segment:\n    question: P02\n",
         "  average_order_value_by_channel_and_segment:\n    question: P02\n    combine: {type: full, keys: [year_month]}\n",
         "uma fonte e `combine`"),                                                              # RVB5B-2-01
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


def _aditividade_contra_a_descricao(doc: dict) -> tuple[list[str], list[str], int]:
    """(sem rótulo, divergentes, conferidas): o começo da descrição de cada coluna de medida, métrica ou
    referência de `consumption` contra a aditividade que `doc` declara."""
    import re
    import yaml
    rotulo = {"Aditiva": "additive", "Semiaditiva": "semi_additive", "Não aditiva": "non_additive"}
    texto = (metrics.sensitivity.ROOT / "dbt" / "models" / "consumption" / "_consumption__models.yml").read_text(encoding="utf-8")
    divergentes, sem_rotulo, conferidas = [], [], 0
    for modelo in yaml.safe_load(texto)["models"]:
        view = doc["views"][modelo["name"]]
        for coluna in modelo.get("columns") or []:
            if metrics.role(coluna["name"], view["columns"][coluna["name"]])[0] not in ("measure", "metric", "reference"):
                continue
            descricao = (coluna.get("description") or "").strip()
            m = re.match(r"(?:\*\*)?(Aditiva|Semiaditiva|Não aditiva)\b", descricao)
            if not m:
                sem_rotulo.append(f"{modelo['name']}.{coluna['name']}")
                continue
            conferidas += 1
            if metrics.additivity(doc, view, coluna["name"]) != rotulo[m.group(1)]:
                divergentes.append(f"{modelo['name']}.{coluna['name']}")
    return sem_rotulo, divergentes, conferidas


def test_a_aditividade_declarada_e_a_do_comeco_da_descricao() -> None:
    """Toda coluna de medida, métrica ou referência de `consumption` começa a descrição pela aditividade, e ela é
    a da declaração (F28; RVB5B-1-01). Sem dispensa: a descrição que traz o bloco do conceito também leva o
    rótulo antes dele (RVB5B-2-02) — herdar o texto do conceito não certifica a classificação."""
    sem_rotulo, divergentes, conferidas = _aditividade_contra_a_descricao(DOC)
    assert sem_rotulo == [] and divergentes == []
    assert conferidas == 88


@pytest.mark.parametrize(("view", "coluna", "para"), [
    pytest.param("repeat_purchase_rate_after_support", "order_count", "additive", id="P16-contagem-entre-categorias"),
    pytest.param("skus_below_reorder_point", "quantity_available", "additive", id="P12-saldo-do-conceito"),
    pytest.param("on_time_delivery_rate_by_carrier", "on_time_rate", "additive", id="P13-taxa-do-conceito"),
])
def test_a_guarda_de_aditividade_recusa_a_classificacao_trocada(view: str, coluna: str, para: str) -> None:
    """Contraprova: trocar só a classificação de uma coluna — inclusive uma descrita pelo bloco do conceito —
    faz a guarda apontar aquela coluna."""
    alterado = copy.deepcopy(DOC)
    colunas = alterado["views"][view]["columns"]
    papel = colunas[coluna]
    if isinstance(papel, str):
        colunas[coluna] = {papel: coluna, "additivity": para}
    else:
        colunas[coluna] = {**papel, ("reference" if "reference" in papel else "additivity"): para}
    assert metrics.additivity(alterado, alterado["views"][view], coluna) == para
    _, divergentes, _ = _aditividade_contra_a_descricao(alterado)
    assert divergentes == [f"{view}.{coluna}"]


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


# ── Os trechos de regra (entrega 4; Q30 a Q32) ───────────────────────────────────

MARCA = "<!-- bigquery: fim do texto curto -->"


def test_a_regra_do_conceito_fica_no_bloco_depois_da_marca() -> None:
    """Q30: o trecho gerado está dentro de um bloco `docs`, depois da marca do texto curto — o que vai ao
    BigQuery (a parte antes da marca) não o leva."""
    import re
    from mvp_ed1.models import export
    for arquivo in DOC["concepts"]:
        texto = (metrics.CATALOG.parent / arquivo).read_text(encoding="utf-8")
        assert texto.count(export.INICIO) == 1, arquivo
        blocos = [m for m in re.finditer(r"\{% docs \w+ %\}(.*?)\{% enddocs %\}", texto, re.S) if export.INICIO in m.group(1)]
        assert len(blocos) == 1, arquivo
        corpo = blocos[0].group(1)
        assert MARCA in corpo and corpo.index(MARCA) < corpo.index(export.INICIO), arquivo


def test_a_regra_do_conceito_cita_cada_medida_e_cada_parte() -> None:
    """A regra do conceito traz as medidas e métricas declaradas e as partes de cada métrica, uma vez cada."""
    for arquivo, nomes in DOC["concepts"].items():
        regra = metrics.concept_rule(DOC, arquivo)
        citadas = [linha.split("`")[1] for linha in regra.splitlines() if linha.startswith("- ")]
        assert len(citadas) == len(set(citadas)) and set(nomes) <= set(citadas), arquivo
        for n in citadas:
            for parte in ("numerator", "denominator", "minuend", "subtrahend"):
                if (DOC["metrics"].get(n) or {}).get(parte):
                    assert citadas.index(DOC["metrics"][n][parte]) < citadas.index(n), (arquivo, n)


def test_a_regra_da_pergunta_cita_as_colunas_e_os_filtros_da_view() -> None:
    """Q32: na view montada, toda medida e métrica tem linha, e todo filtro das medidas aparece pelo rótulo;
    a view por referência diz o teste e a consulta que a conferem."""
    for nome, view in DOC["views"].items():
        regra = metrics.question_rule(DOC, nome)
        if "reference" in view:
            assert view["reference"]["test"] in regra and view["reference"]["query"] in regra, nome
            continue
        for coluna, papel in view["columns"].items():
            papel_nome, alvo = metrics.role(coluna, papel)
            if papel_nome in ("measure", "metric"):
                assert f"- `{coluna if papel_nome == 'measure' else alvo}`" in regra, (nome, coluna)
            if papel_nome == "measure":
                for f in DOC["measures"][alvo].get("filters") or []:
                    assert DOC["filters"][f]["label"] in regra, (nome, f)


# ── A montagem no pacote (Q33; RVB5B-1-02) ───────────────────────────────────────

def test_view_rules_cobre_as_16_views_e_casa_com_as_perguntas() -> None:
    regras = metrics.view_rules(DOC)
    assert set(regras) == {f"consumption.{n}" for n in DOC["views"]}
    from mvp_ed1.models import pacote
    lidas = pacote._perguntas(metrics.sensitivity.ROOT.joinpath(
        "docs", "glossario_de_negocio", "perguntas_de_negocio.md").read_text(encoding="utf-8"))
    for p, q in lidas.items():
        r = regras[q["view"]]
        assert r["question"] == p and r["facts"] == q["facts"] and r["dimensions"] == q["dimensions"], p


@pytest.mark.parametrize("mudar", [
    # As três mutações da revisão: cada uma muda o número da view, e tem de mudar o que o pacote publica.
    pytest.param(lambda d: d["views"]["gross_margin_by_category"]["combine"].update(type="left"), id="P08-full-para-left"),
    pytest.param(lambda d: d["views"]["refund_rate_by_reason"]["combine"].pop("missing"), id="P10-sem-o-zero"),
    pytest.param(lambda d: d["views"]["refund_rate_by_reason"]["sources"][1].update(grain=["year_month"]), id="P10-capturas-so-por-mes"),
])
def test_regra_que_muda_o_numero_muda_o_pacote(mudar) -> None:
    alterado = copy.deepcopy(DOC)
    mudar(alterado)
    assert metrics.view_rules(alterado) != metrics.view_rules(DOC)


# ── Q60: a regra do pedido realizado, escrita à mão e declarada, dizem o mesmo ──

#: O nome com que o glossário escreve cada estado do pedido — os sete, para que um estado indevido na
#: enumeração seja reconhecido e recusado, e não ignorado. É a tradução, não outra declaração da regra.
_ESTADO_EM_PORTUGUES = {"pending": "pendente", "paid": "pago", "picking": "em separação", "shipped": "enviado",
                        "delivered": "entregue", "returned": "devolvido", "cancelled": "cancelado"}


def _enumeracao(lista: str) -> set[str]:
    """Os estados de uma enumeração `a, b, c ou d`, termo a termo e inteiros — `reenviado` não é
    `enviado`. Termo que não é nome de estado nenhum é devolvido como está, e a comparação o acusa."""
    termos = [t.strip(" .`") for parte in lista.split(",") for t in parte.split(" ou ")]
    nomes = {v: k for k, v in _ESTADO_EM_PORTUGUES.items()}
    return {nomes.get(t, f"?{t}") for t in termos if t}


def _enumeracao_da_frase(frase: str) -> set[str]:
    """A lista entre parênteses da frase à mão, até o `;`: `(pago, …, entregue ou devolvido; …)`."""
    return _enumeracao(frase.split("(", 1)[1].split(";", 1)[0].split(")", 1)[0])


def _enumeracao_do_rotulo(rotulo: str) -> set[str]:
    """A lista depois do travessão do rótulo do filtro: `Só pedido realizado — pago, …, devolvido.`"""
    return _enumeracao(rotulo.split("—", 1)[1])


def test_o_pedido_realizado_diz_o_mesmo_a_mao_no_filtro_e_no_modelo() -> None:
    """Q60: a frase à mão do texto curto da receita, o rótulo do filtro `realised_order` e o
    `is_realised` de `trusted.orders` enumeram os mesmos estados — os mesmos, e nenhum a mais."""
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parents[1]
    sql = (raiz / "dbt" / "models" / "trusted" / "orders.sql").read_text(encoding="utf-8")
    lista = re.search(r"p\.order_status in \(([^)]*)\)\s*as is_realised", sql)
    assert lista, "is_realised mudou de forma: atualize a guarda"
    no_modelo = {e.strip(" '") for e in lista.group(1).split(",")}

    receita = (raiz / "docs" / "glossario_de_negocio" / "receita_liquida.md").read_text(encoding="utf-8")
    curto = receita.split("<!-- bigquery: fim do texto curto -->")[0]
    frase = " ".join(curto.split("**Só pedido realizado conta**")[1].split("\n\n")[0].split())
    rotulo = metrics.load_catalog()["filters"]["realised_order"]["label"]

    assert no_modelo == {"paid", "picking", "shipped", "delivered", "returned"}
    assert _enumeracao_da_frase(frase) == no_modelo, frase
    assert _enumeracao_do_rotulo(rotulo) == no_modelo, rotulo


@pytest.mark.parametrize(
    "frase",
    [
        pytest.param("o que chegou a ser pago (pago, em separação, enviado ou entregue; `x`)", id="um-a-menos"),
        pytest.param("o que chegou a ser pago (pago, em separação, reenviado, entregue ou devolvido; `x`)",
                     id="substring-de-um-estado"),
        pytest.param("o que chegou a ser pago (pago, em separação, enviado, entregue, cancelado ou devolvido; `x`)",
                     id="estado-indevido-a-mais"),
        pytest.param("o que chegou a ser pago (pago, em separação, enviado, entregue, devolvido ou estornado; `x`)",
                     id="termo-que-nao-e-estado"),
    ],
)
def test_a_guarda_do_pedido_realizado_acusa_a_enumeracao_errada(frase: str) -> None:
    """Contraprova (RVB5RI-3-01): o estado a menos, a substring, o estado indevido e o termo estranho."""
    assert _enumeracao_da_frase(frase) != {"paid", "picking", "shipped", "delivered", "returned"}
    rotulo = "Só pedido realizado — " + frase.split("(", 1)[1].split(";")[0] + "."
    assert _enumeracao_do_rotulo(rotulo) != {"paid", "picking", "shipped", "delivered", "returned"}
