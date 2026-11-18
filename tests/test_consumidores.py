"""A tabela de Consumidores §5 ("O que mudou para quem consome") na forma que a seção declara (Q70 do plano da reabertura).

O `gdados` achou uma linha de 17/11 antes de uma de 16/11 (17/11/2026, §7): o portal lê a tabela em ordem, e a
seção não dizia nem guardava a ordem. Aqui se guarda o que a regra da seção pede: as linhas em ordem de data (a
data da linha, não a do *commit*), oito colunas, o estado no domínio (`feita`, `prevista`), e a linha `prevista`
sem *commit* nem *build*, porque ela é o aviso de antes da mudança.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CONSUMIDORES = RAIZ / "docs" / "consumidores.md"
CABECALHO = "| Estado | Data | *Commit* | Objeto | Muda | Caso: antes → depois | *Build* do armazém | Achado |"


def _linhas() -> list[list[str]]:
    texto = CONSUMIDORES.read_text(encoding="utf-8").split("\n")
    inicio = texto.index(CABECALHO) + 2
    linhas = []
    for linha in texto[inicio:]:
        if not linha.startswith("| `"):
            break
        # As células, sem a borda; `\|` não aparece nesta tabela.
        linhas.append([c.strip() for c in linha.strip().strip("|").split(" | ")])
    return linhas


def _data(celula: str) -> dt.date:
    return dt.datetime.strptime(celula, "%d/%m/%Y").date()


def test_a_tabela_existe_e_tem_oito_colunas_por_linha() -> None:
    linhas = _linhas()
    assert len(linhas) > 30
    assert [i for i, l in enumerate(linhas) if len(l) != 8] == []


def test_as_linhas_estao_em_ordem_de_data() -> None:
    """Q70: corrigir e guardar. Linhas da mesma data ficam na ordem em que entraram."""
    datas = [_data(l[1]) for l in _linhas()]
    fora = [(i, datas[i - 1].isoformat(), datas[i].isoformat()) for i in range(1, len(datas)) if datas[i] < datas[i - 1]]
    assert fora == [], f"linha antes de uma de data anterior: {fora}"


def test_o_estado_e_o_commit_seguem_a_regra_da_secao() -> None:
    erros = []
    for i, (estado, _, commit, *_resto, build, _achado) in enumerate(_linhas()):
        if estado not in ("`feita`", "`prevista`"):
            erros.append(f"{i}: estado {estado}")
        elif estado == "`prevista`" and (commit != "—" or build != "—"):
            erros.append(f"{i}: `prevista` com commit ou build ({commit}, {build})")
        elif estado == "`feita`" and not re.search(r"`[0-9a-f]{7,}`", commit):
            erros.append(f"{i}: `feita` sem commit ({commit})")
    assert erros == []
