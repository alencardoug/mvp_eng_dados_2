"""A fotografia do ponto de reposição que o alerta usa (ADR-0057; `streaming/ponto.py`).

Sem banco: a leitura do armazém real roda no ciclo, sobre o estado que vai ser descartado.
"""

from __future__ import annotations

import datetime as dt
import json
import pickle

import pytest
import sqlalchemy as sa
import yaml

from mvp_ed1.streaming import config, ponto

AGORA = dt.datetime(2026, 11, 19, 12, 0, tzinfo=dt.timezone.utc)


def test_o_par_ausente_tem_ponto_zero():
    f = ponto.de_linhas([(1, 2, 3), (1, 5, 1)], "analytics.dim_sku_location", AGORA)
    assert (f.ponto(1, 2), f.ponto(1, 5), f.ponto(9, 9)) == (3, 1, 0)


def test_relacao_vazia_para_o_lancamento():
    with pytest.raises(ponto.PontoIndisponivel, match="nenhuma linha"):
        ponto.de_linhas([], "analytics.dim_sku_location", AGORA)


def test_relacao_ausente_para_o_lancamento():
    """Relação que não existe não vira mapa vazio com todos os pontos zero (RVPR-1-02)."""
    motor = sa.create_engine("sqlite://")
    with pytest.raises(ponto.PontoIndisponivel, match="dim_sku_location"):
        ponto.ler_local("analytics.dim_sku_location", "retail", motor=motor)


def test_a_carga_nao_avalia_nenhum_par():
    with pytest.raises(ponto.PainelAoVivoNaCarga):
        ponto.carga().ponto(1, 2)


def test_a_carga_nao_tem_fotografia():
    with pytest.raises(ValueError):
        ponto.Fotografia(ponto.CARGA, ((1, 2, 3),))


def test_a_fotografia_viaja_com_o_dofn_e_e_estavel():
    """Serializada com o `DoFn`, a mesma em toda instância e em todo *worker* reiniciado (RVPR-1-03)."""
    f = ponto.de_linhas([(2, 1, 4), (1, 2, 3)], "r", AGORA)
    g = pickle.loads(pickle.dumps(f))
    assert g.ponto(1, 2) == 3 and g.ponto(2, 1) == 4
    assert g.sha256 == f.sha256 == ponto.de_linhas([(1, 2, 3), (2, 1, 4)], "r", AGORA).sha256


def test_a_fotografia_fica_guardada_com_a_execucao(tmp_path):
    f = ponto.de_linhas([(1, 2, 3)], "analytics.dim_sku_location", AGORA)
    registro = json.loads(f.guardar(tmp_path).read_text(encoding="utf-8"))
    assert registro["modo"] == "fotografia" and registro["pares"] == 1
    assert registro["sha256"] == f.sha256 and registro["pontos"] == [[1, 2, 3]]
    assert json.loads(ponto.carga().guardar(tmp_path).read_text(encoding="utf-8"))["modo"] == "carga"


def test_a_declaracao_aponta_para_o_modelo_do_dbt():
    fluxo = config.carregar()
    assert fluxo.ponto_de_reposicao.qualificado == "analytics.dim_sku_location"
    assert fluxo.ponto_de_reposicao.origem == "retail"


def _fluxo_com_alerta(tmp_path, alerta):
    bruto = yaml.safe_load(config.ARQUIVO.read_text(encoding="utf-8"))
    bruto["alerta"] = alerta
    arquivo = tmp_path / "fluxo.yml"
    arquivo.write_text(yaml.safe_dump(bruto), encoding="utf-8")
    return arquivo


@pytest.mark.parametrize("alerta", [
    {"limiar_de_unidades": 25, "ponto_de_reposicao": {"schema": "a", "tabela": "b", "origem": "retail"}},
    {"ponto_de_reposicao": {"schema": "a", "tabela": "b"}},
    {},
], ids=["segundo-dono", "sem-origem", "sem-ponto"])
def test_a_declaracao_invalida_para_antes_de_subir(tmp_path, alerta):
    config.carregar.cache_clear()
    try:
        with pytest.raises(config.DeclaracaoInvalida):
            config.carregar(_fluxo_com_alerta(tmp_path, alerta))
    finally:
        config.carregar.cache_clear()
