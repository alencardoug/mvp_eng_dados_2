"""O texto próprio da ponte do legado (RVG-1-01) só existe onde `TEXTOS_DA_PONTE` diz, e com o motivo fixo.

Sem banco: lê o `_pontes__models.yml` que `make legacy-models` gerou e chama o
gerador com um par forjado, para provar que ele recusa texto próprio em
coluna que tem par no `stg_retail__*` — a N41 continua valendo para todo o resto.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from mvp_ed1.legacy import ponte

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PONTES = RAIZ / "dbt" / "models" / "trusted" / "legacy" / "_pontes__models.yml"


def _colunas():
    for modelo in yaml.safe_load(PONTES.read_text(encoding="utf-8"))["models"]:
        for coluna in modelo.get("columns") or []:
            yield modelo["name"], coluna


def test_todo_texto_proprio_e_o_da_tabela_e_nao_tem_par() -> None:
    proprios = [(m, c) for m, c in _colunas() if (c.get("meta") or {}).get("description_reason") == ponte.MOTIVO_DA_PONTE]
    assert proprios, "nenhuma coluna com texto próprio: o gerador não escreveu a tabela"
    for modelo, coluna in proprios:
        assert "description_from" not in coluna["meta"], (modelo, coluna["name"])
        assert coluna["description"] == ponte.TEXTOS_DA_PONTE[coluna["name"]], (modelo, coluna["name"])


def test_nenhuma_coluna_fica_sem_texto_nem_declaracao() -> None:
    sem = [(m, c["name"]) for m, c in _colunas()
           if not (c.get("description") or "").strip() and "description_from" not in (c.get("meta") or {})
           and c["name"] in ponte.TEXTOS_DA_PONTE]
    assert sem == []


def test_o_gerador_recusa_texto_proprio_em_coluna_com_par(monkeypatch) -> None:
    original = ponte.pares
    monkeypatch.setattr(ponte, "pares", lambda tabela: [(apelido, True) for apelido, _ in original(tabela)])
    with pytest.raises(ValueError, match="tem par no staging"):
        ponte.models_yml()
