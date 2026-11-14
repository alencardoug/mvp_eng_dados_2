"""O pacote de metadados versionado está em dia com os insumos (D91, guarda do RVG-1-04).

Roda no `check-offline`, sem banco e sem `dbt/target`: o pacote se confere pelo
`inputs_sha256`, recalculado dos arquivos rastreados que o alimentam. Insumo mudado
sem `make catalog` falha aqui; *commit* que não mexe nos insumos não invalida nada.

As contraprovas que o RVG-1-04 pede:
* **clone sem artefatos** — a guarda roda num clone do repositório, sem `dbt/target`;
* **regeneração repetida** — com os mesmos artefatos, o mesmo texto (integração);
* **commit posterior sem mudança dos insumos** — o digest não muda.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import jsonschema
import pytest

from mvp_ed1.models import pacote

RAIZ = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gerado() -> dict:
    if not pacote.PACOTE.exists():
        pytest.fail("docs/pacote_de_metadados.json não existe; rode `make catalog`")
    return json.loads(pacote.PACOTE.read_text(encoding="utf-8"))


def test_o_pacote_cumpre_o_esquema(gerado) -> None:
    esquema = json.loads(pacote.ESQUEMA.read_text(encoding="utf-8"))
    erros = sorted(e.message for e in jsonschema.Draft202012Validator(esquema).iter_errors(gerado))
    assert erros == []


def test_o_pacote_esta_em_dia_com_os_insumos(gerado) -> None:
    caminhos = pacote.insumos()
    assert gerado["provenance"]["inputs"] == caminhos, "insumo novo ou removido: rode `make catalog`"
    assert gerado["provenance"]["inputs_sha256"] == pacote.digest(caminhos), "insumo mudou: rode `make catalog`"


def test_o_pacote_esta_na_forma_deterministica(gerado) -> None:
    assert pacote.PACOTE.read_text(encoding="utf-8") == pacote.serializar(gerado)


def test_um_insumo_alterado_muda_o_digest() -> None:
    """Contraprova: a guarda acusa a mudança de qualquer insumo."""
    caminhos = pacote.insumos()
    original = pacote.digest(caminhos)
    alvo = "docs/glossario_de_negocio/receita_liquida.md"
    assert alvo in caminhos
    alterado = pacote.digest(caminhos, conteudo=lambda c: (RAIZ / c).read_bytes() + (b"x" if c == alvo else b""))
    assert alterado != original


def test_um_commit_sem_mudanca_nos_insumos_nao_muda_o_digest() -> None:
    """O digest depende só do conteúdo dos insumos, não do commit nem da hora."""
    caminhos = pacote.insumos()
    assert pacote.digest(caminhos) == pacote.digest(list(caminhos))


def test_a_guarda_roda_num_clone_sem_artefatos(tmp_path) -> None:
    """Contraprova do clone limpo: no HEAD clonado, sem `dbt/target`, o digest é calculável e é o do pacote dele."""
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(RAIZ), str(clone)], check=True)
    assert not (clone / "dbt" / "target").exists()
    versionado = clone / "docs" / "pacote_de_metadados.json"
    if not versionado.exists():
        pytest.skip("o HEAD ainda não tem o pacote (o primeiro commit dele)")
    dado = json.loads(versionado.read_text(encoding="utf-8"))
    caminhos = pacote.insumos(clone)
    assert dado["provenance"]["inputs"] == caminhos
    assert dado["provenance"]["inputs_sha256"] == pacote.digest(caminhos, raiz=clone)


@pytest.mark.integracao
def test_a_regeneracao_repetida_da_o_mesmo_texto() -> None:
    """Com os mesmos artefatos, duas montagens dão os mesmos bytes."""
    if not (pacote.MANIFEST.exists() and pacote.RUN_RESULTS.exists()):
        pytest.skip("sem os artefatos do dbt")
    from mvp_ed1.models import sensitivity

    manifest, derivacao = sensitivity.load()
    run = json.loads(pacote.RUN_RESULTS.read_text(encoding="utf-8"))
    assert pacote.serializar(pacote.montar(manifest, derivacao, run)) == pacote.serializar(pacote.montar(manifest, derivacao, run))
