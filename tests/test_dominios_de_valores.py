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
    av = next(t for t in cols["gateway_response_code"]["data_tests"] if isinstance(t, dict))
    assert av["accepted_values"]["arguments"]["values"] == ["00", "05"]


def test_o_nulo_fica_fora_do_mapa_e_decide_o_not_null() -> None:
    cols = _colunas(_aplicar())
    assert "not_null" in cols["order_status"]["data_tests"]
    assert "not_null" in cols["gateway_response_code"]["data_tests"]            # sem `null_meaning`: ganha
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
