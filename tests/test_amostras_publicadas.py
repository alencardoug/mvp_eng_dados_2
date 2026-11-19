"""O arquivo das amostras versionado, sem banco (ADR-0058, segunda retificação): o esquema, a cobertura igual ao
conjunto de relações do pacote e a máscara estrutural. Entra no repositório **com** o arquivo, no Bloco 4 do plano
do ponto de reposição; antes dele, o arquivo não existe. A conferência contra o armazém é a do `make
amostras-check`, na invocação que o arquivo cita."""

from __future__ import annotations

import json
import pathlib

import jsonschema

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "docs/amostras_de_registros.json"
ESQUEMA = RAIZ / "docs/amostras_de_registros.schema.json"
PACOTE = RAIZ / "docs/pacote_de_metadados.json"


def _carregar(caminho: pathlib.Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_o_arquivo_valida_contra_o_esquema_do_mesmo_commit() -> None:
    jsonschema.validate(_carregar(ARQUIVO), _carregar(ESQUEMA))


def test_a_cobertura_e_o_pacote_da_mesma_publicacao() -> None:
    amostras, pacote = _carregar(ARQUIVO), _carregar(PACOTE)
    assert set(amostras["relations"]) == set(pacote["relations"])
    for nome, r in amostras["relations"].items():
        assert r["columns"] == list(pacote["relations"][nome]["columns"]), nome


def test_toda_celula_de_coluna_pessoal_e_marcador_ou_nulo() -> None:
    """A máscara estrutural: nas colunas `personal` fora dos recipientes do legado, só o marcador ou o nulo."""
    amostras, pacote = _carregar(ARQUIVO), _carregar(PACOTE)
    marcador = amostras["masking"]["marker"]
    recipientes = {"original_payload", "cleaned_payload", "payloads", "last_payload", "findings"}
    expostas = []
    for nome, r in amostras["relations"].items():
        pessoais = {c for c, m in pacote["relations"][nome]["columns"].items() if m.get("sensitivity") == "personal"}
        assert set(r["masked_columns"]) == pessoais, nome
        for i, linha in enumerate(r["rows"]):
            for coluna, valor in zip(r["columns"], linha):
                if coluna in pessoais and coluna not in recipientes and valor not in (None, marcador):
                    expostas.append(f"{nome}[{i}].{coluna}")
    assert expostas == [], expostas[:20]
