"""O escritor dos domínios de valores (F7; plano da base dos consumidores, Bloco 5, item 13 — as sondas).

Cada teste é uma das sondas que o desenho pediu antes do ADR: o código com zero à esquerda, o nulo fora do
mapa, o domínio alterado e removido, a idempotência, os testes que já existem nas formas de bloco e de
fluxo, a chave repetida e o texto com quebra de linha. Os `.yml` são textos em memória; o catálogo também.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from mvp_ed1.models import value_domains as vd

CAMINHO = pathlib.Path("/tmp/_analytics__models.yml")

YML = """version: 2
models:
  - name: fact_x
    columns:
      - name: order_status
        description: "Estado do pedido."
        meta:
          sensitivity: public
          value_domain: order_status
        data_tests:
          - not_null
          - accepted_values:
              values: [pending, paid]
      - name: from_status
        meta:
          sensitivity: public
          value_domain: order_status
          null_meaning: "O primeiro evento do pedido não tem estado anterior."
      - name: gateway_response_code
        meta:
          sensitivity: internal
          value_domain: gateway_response_code
"""


def _pedido(dominio: str, valores: dict[str, str], not_null: bool = True) -> dict:
    return {"domain": dominio, "values": valores, "accepted": sorted(valores), "not_null": not_null}


ESTADOS = {"pending": "Aguardando pagamento.", "paid": "Pago."}
CODIGOS = {"00": "Código sorteado pelo gerador.", "05": "Código sorteado pelo gerador."}


def _colunas(texto: str) -> dict:
    return {c["name"]: c for c in yaml.safe_load(texto)["models"][0]["columns"]}


def _aplicar(texto: str = YML) -> str:
    return vd.patch_value_domains(texto, {"fact_x": {
        "order_status": _pedido("order_status", ESTADOS),
        "from_status": _pedido("order_status", ESTADOS, not_null=False),
        "gateway_response_code": _pedido("gateway_response_code", CODIGOS)}})


def test_o_codigo_com_zero_a_esquerda_continua_texto() -> None:
    cols = _colunas(_aplicar())
    assert cols["gateway_response_code"]["meta"]["values"] == CODIGOS
    av = next(t for t in cols["gateway_response_code"]["data_tests"] if vd._marcado(t, "accepted_values"))
    assert av["accepted_values"]["arguments"]["values"] == ["00", "05"]


def test_o_nulo_fica_fora_do_mapa_e_decide_o_not_null() -> None:
    cols = _colunas(_aplicar())
    assert "not_null" in cols["order_status"]["data_tests"]
    assert any(vd._marcado(t, "not_null") for t in cols["gateway_response_code"]["data_tests"])  # sem `null_meaning`: ganha, marcado
    assert "not_null" not in (cols["from_status"].get("data_tests") or [])      # com `null_meaning`: não
    assert None not in cols["from_status"]["meta"]["values"] and "None" not in cols["from_status"]["meta"]["values"]


def test_not_null_a_mao_com_null_meaning_e_recusa() -> None:
    texto = YML.replace('null_meaning: "O primeiro evento do pedido não tem estado anterior."',
                        'null_meaning: "x"\n        data_tests:\n          - not_null')
    with pytest.raises(ValueError, match="null_meaning"):
        _aplicar(texto)


def test_o_accepted_values_a_mao_e_substituido_sem_duplicar() -> None:
    cols = _colunas(_aplicar())
    aceitos = [t for t in cols["order_status"]["data_tests"] if isinstance(t, dict) and "accepted_values" in t]
    assert len(aceitos) == 1 and vd._marcado(aceitos[0])
    assert aceitos[0]["accepted_values"]["arguments"]["values"] == ["paid", "pending"]


def test_a_linha_vazia_e_o_comentario_ficam_fora_do_bloco_escrito() -> None:
    """A linha vazia do fim de um bloco pertence ao que vem depois: não entra no `meta` nem fica entre itens."""
    texto = YML.replace("      - name: from_status", "\n      # o estado anterior\n      - name: from_status") + "\n"
    saida = _aplicar(texto)
    assert "\n\n          values:" not in saida and "\n\n        data_tests:" not in saida
    assert "\n\n      # o estado anterior\n      - name: from_status" in saida
    assert saida.endswith("value_domain: gateway_response_code\n\n")


def test_duas_geracoes_nao_mudam_nada() -> None:
    uma = _aplicar()
    assert _aplicar(uma) == uma


def test_o_dominio_alterado_troca_a_subarvore_inteira() -> None:
    uma = _aplicar()
    menor = {"pending": "Aguardando."}
    outra = vd.patch_value_domains(uma, {"fact_x": {"order_status": _pedido("order_status", menor)}})
    cols = _colunas(outra)
    assert cols["order_status"]["meta"]["values"] == menor                     # sem filho antigo
    assert "paid" not in outra.split("- name: from_status")[0]


def test_a_ligacao_removida_leva_o_derivado_e_preserva_o_que_e_a_mao() -> None:
    uma = _aplicar()
    sem = vd.patch_value_domains(uma, {}, {"fact_x": ["order_status"]})
    col = _colunas(sem)["order_status"]
    assert "values" not in col["meta"]
    assert col["data_tests"] == ["not_null"]                                    # o `not_null` à mão fica
    assert col["description"] == "Estado do pedido."


@pytest.mark.parametrize("forma", ["meta: {sensitivity: public, value_domain: order_status}",
                                   "data_tests: [not_null]"])
def test_a_forma_em_linha_e_recusada(forma: str) -> None:
    texto = """version: 2
models:
  - name: fact_x
    columns:
      - name: order_status
        meta:
          value_domain: order_status
""" if forma.startswith("data_tests") else """version: 2
models:
  - name: fact_x
    columns:
      - name: order_status
"""
    texto += "        " + forma + "\n"
    with pytest.raises(ValueError, match="em linha|sem `meta` em bloco"):
        vd.patch_value_domains(texto, {"fact_x": {"order_status": _pedido("order_status", ESTADOS)}})


def test_o_significado_com_quebra_de_linha_e_dois_pontos_volta_igual() -> None:
    valores = {"lost": "Extraviada: a transportadora\nnão entregou."}
    texto = vd.patch_value_domains(YML, {"fact_x": {"order_status": _pedido("order_status", valores)}})
    assert _colunas(texto)["order_status"]["meta"]["values"] == valores


CATALOGO = """domains:
  gateway_response_code:
    description: "Código de retorno do adquirente."
    values:
      "00": {meaning: "Sorteado.", source: "generator/geracao.yml"}
"""


def test_o_catalogo_recusa_o_codigo_sem_aspas_e_a_chave_repetida(tmp_path) -> None:
    assert vd.load_catalog(tmp_path / "d.yml", CATALOGO)["domains"]["gateway_response_code"]["values"]["00"]
    with pytest.raises(ValueError, match="não é texto"):
        vd.load_catalog(tmp_path / "d.yml", CATALOGO.replace('"00"', "00"))
    with pytest.raises(ValueError):
        vd.load_catalog(tmp_path / "d.yml", CATALOGO + '      "00": {meaning: "B.", source: "x"}\n')
    with pytest.raises(ValueError, match="meaning"):
        vd.load_catalog(tmp_path / "d.yml", CATALOGO.replace(', source: "generator/geracao.yml"', ""))


def test_a_ligacao_confere_impossiveis_e_nao_observados() -> None:
    catalogo = {"domains": {"order_status": {"values": {k: {"meaning": v, "source": "s"} for k, v in ESTADOS.items()}}}}
    base = dict(path=CAMINHO, model="fact_x", column="from_status", domain="order_status", null_meaning=None)
    assert vd.allowed(vd.Link(**base, impossible={"paid": "terminal"}, not_observed={}), catalogo) == {"pending": "Aguardando pagamento."}
    with pytest.raises(ValueError, match="fora do domínio"):
        vd.allowed(vd.Link(**base, impossible={"lost": "x"}, not_observed={}), catalogo)
    with pytest.raises(ValueError, match="em `impossible` e em `not_observed`"):
        vd.allowed(vd.Link(**base, impossible={"paid": "x"}, not_observed={"paid": "y"}), catalogo)
    with pytest.raises(ValueError, match="motivo"):
        vd.allowed(vd.Link(**base, impossible={"paid": ""}, not_observed={}), catalogo)
    with pytest.raises(ValueError, match="não existe"):
        vd.allowed(vd.Link(**{**base, "domain": "outro"}, impossible={}, not_observed={}), catalogo)


def test_o_dominio_sem_ligacao_falha_salvo_reservado() -> None:
    catalogo = {"domains": {"a": {"values": {}}, "b": {"values": {}, "reserved": "uso futuro"}}}
    assert vd.orphan_domains(catalogo, []) == ["a"]


# ── O membro desconhecido (Bloco 5, item 1: o sentinela fora do domínio) ──────────

def _com_membro() -> dict:
    return {"domains": {"ibge_region": {"values": {"Sul": {"meaning": "Região Sul.", "source": "s"}}}},
            "unknown_members": {"dim_geography": {"meaning": "Sem endereço.", "source": "dim_geography.sql",
                                                   "columns": {"region": "Desconhecido", "country": "ZZ"}}}}


def _ligacao(model: str, column: str, unknown_member: str | None = None) -> vd.Link:
    return vd.Link(path=CAMINHO, model=model, column=column, domain="ibge_region", null_meaning=None,
                   impossible={}, not_observed={}, unknown_member=unknown_member)


def test_a_coluna_da_propria_dimensao_herda_o_sentinela() -> None:
    permitidos = vd.allowed(_ligacao("dim_geography", "region"), _com_membro())
    assert permitidos == {"Sul": "Região Sul.", "Desconhecido": "Membro desconhecido — Sem endereço."}


def test_a_coluna_que_propaga_o_membro_o_declara_e_a_que_nao_propaga_nao_o_tem() -> None:
    assert "Desconhecido" in vd.allowed(_ligacao("revenue_by_delivery_region", "region", "dim_geography.region"), _com_membro())
    assert vd.allowed(_ligacao("dim_warehouse", "warehouse_region"), _com_membro()) == {"Sul": "Região Sul."}


def test_unknown_member_que_sobra_ou_que_nao_existe_e_recusado() -> None:
    with pytest.raises(ValueError, match="sobra"):
        vd.allowed(_ligacao("dim_geography", "region", "dim_geography.region"), _com_membro())
    with pytest.raises(ValueError, match="não existe"):
        vd.allowed(_ligacao("revenue_by_delivery_region", "region", "dim_geography.state_name"), _com_membro())


def test_o_sentinela_que_colide_com_um_valor_do_dominio_e_recusado() -> None:
    catalogo = _com_membro()
    catalogo["unknown_members"]["dim_geography"]["columns"]["region"] = "Sul"
    with pytest.raises(ValueError, match="colide"):
        vd.allowed(_ligacao("dim_geography", "region"), catalogo)


def test_o_catalogo_recusa_membro_sem_significado_e_sentinela_que_nao_e_texto(tmp_path) -> None:
    base = CATALOGO + 'unknown_members:\n  dim_x:\n    meaning: "M."\n    source: "x.sql"\n    columns:\n      natural_key: "-1"\n'
    assert vd.load_catalog(tmp_path / "d.yml", base)["unknown_members"]["dim_x"]["columns"]["natural_key"] == "-1"
    with pytest.raises(ValueError, match="não é texto"):
        vd.load_catalog(tmp_path / "d.yml", base.replace('natural_key: "-1"', "natural_key: -1"))
    with pytest.raises(ValueError, match="meaning"):
        vd.load_catalog(tmp_path / "d.yml", base.replace('    meaning: "M."\n', ""))


def test_o_catalogo_do_repositorio_carrega_e_cada_dominio_tem_ligacao() -> None:
    """O `dominios.yml` versionado, lido estrito; a guarda de domínio órfão é a do `make catalog`."""
    catalogo = vd.load_catalog()
    assert set(catalogo["unknown_members"]) == {"dim_geography", "dim_sales_channel", "dim_support_agent"}
    from mvp_ed1.models import descriptions
    ligacoes = vd.links(descriptions.disk_entries())
    assert vd.orphan_domains(catalogo, ligacoes) == []
    for ligacao in ligacoes:
        vd.allowed(ligacao, catalogo)


# ── A cobertura (Bloco 5, item 3) ─────────────────────────────────────────────────

def _regras() -> dict:
    return {"exclusions": {
        "by_type": {"number": {"types": ["bigint"], "reason": "r"}},
        "by_name": {"key": {"suffixes": ["_key"], "reason": "r"}, "code": {"suffixes": ["_code"], "reason": "r"},
                    "geo": {"names": ["state_code"], "reason": "r"}},
        "exceptions": {"dim_x.nota": "texto livre"}}}


def test_a_cobertura_exige_exatamente_uma_classificacao() -> None:
    colunas = [("analytics", "dim_x", "x_key", "text"), ("analytics", "dim_x", "x_id", "bigint"),
               ("analytics", "dim_x", "status", "text"), ("analytics", "dim_x", "nota", "text"),
               ("analytics", "dim_x", "carrier_code", "text")]
    classificadas, problemas = vd.coverage(colunas, {("dim_x", "status")}, _regras())
    assert classificadas == {"analytics.dim_x.x_key": "key", "analytics.dim_x.x_id": "number",
                             "analytics.dim_x.status": "value_domain", "analytics.dim_x.nota": "exception",
                             "analytics.dim_x.carrier_code": "code"}
    assert problemas == []


def test_coluna_em_duas_regras_ou_em_nenhuma_falha() -> None:
    colunas = [("analytics", "dim_x", "state_code", "text"), ("analytics", "dim_x", "nome", "text"),
               ("analytics", "dim_x", "x_flag", "boolean")]
    _, problemas = vd.coverage(colunas, set(), _regras())
    assert problemas == ["analytics.dim_x.state_code (text): duas regras: code, geo",
                         "analytics.dim_x.nome (text): nenhuma regra",
                         "analytics.dim_x.x_flag (boolean): nenhuma regra"]


def test_o_catalogo_recusa_regra_e_excecao_sem_motivo(tmp_path) -> None:
    base = CATALOGO + "exclusions:\n  by_type:\n    number: {types: [bigint], reason: \"N.\"}\n  exceptions:\n    dim_x.nota: \"Livre.\"\n"
    assert vd.load_catalog(tmp_path / "d.yml", base)["exclusions"]["exceptions"] == {"dim_x.nota": "Livre."}
    with pytest.raises(ValueError, match="sem `reason`"):
        vd.load_catalog(tmp_path / "d.yml", base.replace(', reason: "N."', ""))
    with pytest.raises(ValueError, match="sem motivo"):
        vd.load_catalog(tmp_path / "d.yml", base.replace('"Livre."', '""'))


# ── A revisão da implementação, rodada 1 (RVB5A-1-01 a 03) ───────────────────────

def test_o_not_null_derivado_tem_a_marca_e_o_a_mao_nao() -> None:
    cols = _colunas(_aplicar())
    assert "not_null" in cols["order_status"]["data_tests"]                     # o à mão continua texto solto
    derivados = [t for t in cols["gateway_response_code"]["data_tests"] if vd._marcado(t, "not_null")]
    assert derivados == [{"not_null": {"config": {"meta": {"value_domain": "gateway_response_code"}}}}]


def test_a_remocao_leva_o_not_null_derivado_e_fica_o_a_mao() -> None:
    sem = vd.patch_value_domains(_aplicar(), {}, {"fact_x": ["order_status", "gateway_response_code"]})
    cols = _colunas(sem)
    assert cols["order_status"]["data_tests"] == ["not_null"]
    assert "data_tests" not in cols["gateway_response_code"]                    # sem item, sem a chave
    vd.verify(CAMINHO, sem, {}, {"fact_x": ["order_status", "gateway_response_code"]})


def test_a_remocao_na_coluna_que_admite_nulo_nao_deixa_data_tests_vazio() -> None:
    """RVB5A-1-01: o único teste era o `accepted_values` derivado; a chave sai junto, e a segunda passada não muda nada."""
    sem = vd.patch_value_domains(_aplicar(), {}, {"fact_x": ["from_status"]})
    assert "data_tests" not in _colunas(sem)["from_status"]
    assert vd.patch_value_domains(sem, {}, {"fact_x": ["from_status"]}) == sem
    vd.verify(CAMINHO, sem, {}, {"fact_x": ["from_status"]})


def test_o_verify_recusa_data_tests_nulo() -> None:
    quebrado = YML.replace('null_meaning: "O primeiro evento do pedido não tem estado anterior."',
                           'null_meaning: "O primeiro evento do pedido não tem estado anterior."\n        data_tests:', 1)
    with pytest.raises(RuntimeError, match="não é uma lista|sem lista"):
        vd.verify(CAMINHO, quebrado, {"fact_x": {"from_status": _pedido("order_status", ESTADOS, not_null=False)}})


def test_acrescentar_null_meaning_tira_o_not_null_derivado_sem_recusar() -> None:
    """RVB5A-1-02: o derivado sai sozinho; só o `not_null` à mão contra `null_meaning` é recusado."""
    uma = _aplicar()
    outra = vd.patch_value_domains(uma, {"fact_x": {"gateway_response_code": _pedido("gateway_response_code", CODIGOS, not_null=False)}})
    testes = _colunas(outra)["gateway_response_code"]["data_tests"]
    assert not any(vd._marcado(t, "not_null") for t in testes) and "not_null" not in testes
    vd.verify(CAMINHO, outra, {"fact_x": {"gateway_response_code": _pedido("gateway_response_code", CODIGOS, not_null=False)}})


def test_o_catalogo_ausente_com_ligacao_no_disco_recusa(tmp_path, monkeypatch, capsys) -> None:
    """RVB5A-1-03: sem `dominios.yml`, só o projeto sem domínio nenhum passa; com ligação, o `main` recusa."""
    import json
    from mvp_ed1.models import sensitivity as s
    dbt = tmp_path / "dbt"
    (dbt / "models" / "analytics").mkdir(parents=True)
    (dbt / "target").mkdir()
    monkeypatch.setattr(s, "ROOT", tmp_path)
    monkeypatch.setattr(s, "DBT", dbt)
    monkeypatch.setattr(s, "MANIFEST", dbt / "target" / "manifest.json")
    monkeypatch.setattr(s, "CACHE", tmp_path / "derivation.pickle")
    no = {"unique_id": "model.mvp_ed1.fact_x", "resource_type": "model", "name": "fact_x", "schema": "analytics",
          "database": "wh", "original_file_path": "models/analytics/fact_x.sql", "depends_on": {"nodes": []},
          "columns": {}, "compiled_code": "select 'paid' as order_status", "raw_code": "select 'paid' as order_status\n"}
    (dbt / "models" / "analytics" / "fact_x.sql").write_text(no["raw_code"], encoding="utf-8")
    s.MANIFEST.write_text(json.dumps({"metadata": {"project_name": "mvp_ed1"}, "sources": {},
                                      "nodes": {no["unique_id"]: no}}), encoding="utf-8")
    yml = dbt / "models" / "analytics" / "_analytics__models.yml"
    yml.write_text("version: 2\nmodels:\n  - name: fact_x\n    columns:\n      - name: order_status\n        meta:\n"
                   "          sensitivity: public\n          value_domain: order_status\n", encoding="utf-8")
    for argv in ([], ["--check"]):
        assert s.main(argv) == 1
        assert "ausente" in capsys.readouterr().err


# ── A revisão da implementação, rodada 2 (RVB5A-2-01 e 02) ───────────────────────

COMENTARIO = "          - not_null  # teste manual; independente de value_domain: order_status"


def test_comentario_com_value_domain_nao_faz_o_not_null_a_mao_derivado() -> None:
    """RVB5A-2-01: a procedência é a da estrutura; o manual fica na remoção e contradiz o `null_meaning`."""
    texto = _aplicar().replace("          - not_null\n", COMENTARIO + "\n", 1)
    sem = vd.patch_value_domains(texto, {}, {"fact_x": ["order_status"]})
    assert _colunas(sem)["order_status"]["data_tests"] == ["not_null"]
    vd.verify(CAMINHO, sem, {}, {"fact_x": ["order_status"]})
    with pytest.raises(ValueError, match="à mão"):
        vd.patch_value_domains(texto, {"fact_x": {"order_status": _pedido("order_status", ESTADOS, not_null=False)}})


DESLIGADO = "          - not_null:\n              config:\n                enabled: false"


@pytest.mark.parametrize("com_derivado", [False, True])
def test_not_null_a_mao_desligado_nao_vale_e_e_recusado(com_derivado: bool) -> None:
    """RVB5A-2-02: o `enabled: false` não é garantia; o escritor e o `verify` recusam, com ou sem o derivado junto."""
    derivado = "\n          - not_null:\n              config:\n                meta:\n                  value_domain: order_status"
    texto = _aplicar().replace("          - not_null\n", DESLIGADO + (derivado if com_derivado else "") + "\n", 1)
    assert (sum(1 for t in _colunas(texto)["order_status"]["data_tests"] if vd._marcado(t, "not_null")) == 1) == com_derivado
    with pytest.raises(ValueError, match="desligado"):
        vd.patch_value_domains(texto, {"fact_x": {"order_status": _pedido("order_status", ESTADOS)}})
    with pytest.raises(RuntimeError, match="desligado"):
        vd.verify(CAMINHO, texto, {"fact_x": {"order_status": _pedido("order_status", ESTADOS)}})
