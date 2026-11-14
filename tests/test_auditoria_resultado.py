"""O resultado declarado da auditoria das views (Bloco 1b) cobre as 16 e aponta para o que existe.

Sem banco: é o que o pacote de metadados lê para o campo `view_audits`. O que prova cada linha
é `tests/test_auditoria_das_views.py`, que precisa do armazém.
"""

from __future__ import annotations

import pathlib
import re

import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[1]
RESULTADO = yaml.safe_load((RAIZ / "tests/auditoria/resultado.yml").read_text(encoding="utf-8"))
VIEWS = {p.stem for p in (RAIZ / "dbt/models/consumption").glob("*.sql")}


def test_o_resultado_cobre_as_dezesseis_views() -> None:
    assert set(RESULTADO["views"]) == VIEWS


def test_os_criterios_sao_os_tres_do_formato() -> None:
    assert RESULTADO["criteria"] == ["non_additivity", "time_dependent_balance", "truncated_population"]
    assert re.fullmatch(r"[0-9a-f]{7,40}", RESULTADO["commit"])


def test_cada_referencia_e_populacao_existe() -> None:
    def caminhos(linha):
        for chave in ("reference", "population"):
            valor = linha.get(chave) or []
            yield from ([valor] if isinstance(valor, str) else valor)

    faltam = [c for linha in RESULTADO["views"].values() for c in caminhos(linha) if not (RAIZ / c).exists()]
    assert faltam == []


def test_cada_achado_citado_existe_nos_achados() -> None:
    achados = set(re.findall(r"^### (F\d+) —", (RAIZ / "docs/achados_nl_sql.md").read_text(encoding="utf-8"), re.M))
    citados = {f for linha in RESULTADO["views"].values() for f in linha["findings"]}
    assert citados <= achados, sorted(citados - achados)
