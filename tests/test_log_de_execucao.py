"""O log de execução e a regra da procedência do armazém (ADR-0054).

A regra de leitura é uma só, a *view* `governance.warehouse_provenance`, e é ela que se prova aqui: cada
motivo de `not_verified`, a ordem pela `sequence` (e não pelo relógio), a linha aberta que bloqueia, a
abandonada, a sobreposição, e o único caso `verified`. As linhas são montadas num armazém **efêmero**,
como o dbt e `registrar_mutacao` as escreveriam. O caminho do dbt de verdade — o `make dbt-build` que
registra, o `--select` parcial, o `dbt test` que não registra — foi exercitado no armazém de trabalho e
está no registro da entrega; o teste singular `governanca_execucao_aberta_visivel` o confere em todo build.
"""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest
from sqlalchemy import create_engine, text

from mvp_ed1 import governance
from mvp_ed1.db import WAREHOUSE, database_url
from mvp_ed1.models import pacote

COMMIT = "a" * 40


# ── Sem banco ────────────────────────────────────────────────────────────────────

def test_o_git_do_ambiente_so_aceita_commit_completo_e_sujeira_booleana() -> None:
    assert governance._git_do_ambiente({"MVP_GIT_COMMIT": COMMIT, "MVP_GIT_TREE_DIRTY": "false"}) == (COMMIT, False)
    assert governance._git_do_ambiente({"MVP_GIT_COMMIT": COMMIT, "MVP_GIT_TREE_DIRTY": "TRUE"}) == (COMMIT, True)
    assert governance._git_do_ambiente({}) == (None, None)                                   # a DAG
    assert governance._git_do_ambiente({"MVP_GIT_COMMIT": "abc", "MVP_GIT_TREE_DIRTY": "talvez"}) == (None, None)


def _repo(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / ".gitignore").write_text("dbt/target/\n", encoding="utf-8")
    (tmp_path / "dbt" / "models").mkdir(parents=True)
    (tmp_path / "dbt" / "models" / "a.sql").write_text("select 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "x")
    return git


def test_a_sujeira_do_build_conta_o_nao_rastreado_dos_insumos_do_dbt(tmp_path) -> None:
    """RVL5-2-04: o modelo novo fora do Git entra no build e não passa por limpo; o artefato ignorado, sim."""
    _repo(tmp_path)
    assert pacote.sujeira_do_build(tmp_path) == "false"
    (tmp_path / "dbt" / "target").mkdir()
    (tmp_path / "dbt" / "target" / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "solto.txt").write_text("fora dos insumos do dbt\n", encoding="utf-8")
    assert pacote.sujeira_do_build(tmp_path) == "false"
    (tmp_path / "dbt" / "models" / "novo.sql").write_text("select 2\n", encoding="utf-8")
    assert pacote.sujeira_do_build(tmp_path) == "true"                                  # não rastreado
    (tmp_path / "dbt" / "models" / "novo.sql").unlink()
    (tmp_path / "dbt" / "models" / "a.sql").write_text("select 3\n", encoding="utf-8")
    assert pacote.sujeira_do_build(tmp_path) == "true"                                  # rastreado mudado
    assert len(pacote.commit_atual(tmp_path)) == 40


# ── No armazém efêmero ──────────────────────────────────────────────────────────

@pytest.fixture
def armazem():
    if not os.environ.get("WAREHOUSE_DB_PASSWORD"):
        pytest.skip("ambiente sem .env carregado; rode por `make test`")
    administrador = create_engine(database_url(WAREHOUSE), isolation_level="AUTOCOMMIT")
    nome = f"warehouse_teste_log_{uuid.uuid4().hex[:8]}"
    try:
        with administrador.connect() as conexao:
            conexao.execute(text(f'create database "{nome}"'))
    except Exception as erro:  # pragma: no cover
        pytest.skip(f"armazém indisponível: {erro}")
    anterior = os.environ["WAREHOUSE_DB_NAME"]
    os.environ["WAREHOUSE_DB_NAME"] = nome
    motor = create_engine(database_url(WAREHOUSE))
    try:
        governance.garantir(motor)
        yield motor
    finally:
        motor.dispose()
        os.environ["WAREHOUSE_DB_NAME"] = anterior
        with administrador.connect() as conexao:
            conexao.execute(text(f'drop database if exists "{nome}" with (force)'))
        administrador.dispose()


def _linha(motor, **campos) -> str:
    """Uma execução como o dbt a deixaria; por padrão, a que verifica."""
    linha = {"invocation_id": str(uuid.uuid4()), "command": "build", "git_commit": COMMIT, "git_tree_dirty": False,
             "inputs_confirmed": True, "full_build": True, "status": "success"} | campos
    colunas = ", ".join(linha)
    fecho = "" if linha["status"] in ("started", "abandoned") else ", finished_at"
    agora = "" if linha["status"] in ("started", "abandoned") else ", clock_timestamp()"
    abandono = ", abandoned_at" if linha["status"] == "abandoned" else ""
    agora_abandono = ", clock_timestamp()" if linha["status"] == "abandoned" else ""
    with motor.begin() as conexao:
        conexao.execute(text(f"insert into {governance.LOG} ({colunas}{fecho}{abandono}) "
                             f"values ({', '.join(':' + c for c in linha)}{agora}{agora_abandono})"), linha)
    return linha["invocation_id"]


def _estado(motor) -> tuple[str, str | None]:
    p = governance.procedencia(motor)
    return p["status"], p["reason"]


@pytest.mark.integracao
def test_a_migracao_cria_o_log_e_a_view_e_nao_repete(armazem) -> None:
    assert "0003_dbt_invocations" in governance.versoes(armazem)
    assert governance.garantir(armazem) == []
    assert _estado(armazem) == ("not_verified", "no_execution")


@pytest.mark.integracao
def test_so_o_build_integral_limpo_e_confirmado_verifica(armazem) -> None:
    _linha(armazem)
    assert _estado(armazem) == ("verified", None)
    for campos, motivo in (({"full_build": False}, "partial_execution"),
                           ({"status": "failed"}, "failed_execution"),
                           ({"git_commit": None}, "unknown_commit"),
                           ({"git_tree_dirty": True}, "dirty_tree"),
                           ({"git_tree_dirty": None}, "dirty_tree"),
                           ({"inputs_confirmed": False}, "inputs_not_confirmed")):
        _linha(armazem, **campos)
        assert _estado(armazem) == ("not_verified", motivo), campos
    _linha(armazem)                                     # um build integral novo supera tudo que fechou
    assert _estado(armazem) == ("verified", None)


@pytest.mark.integracao
def test_a_linha_aberta_bloqueia_ate_ser_abandonada_e_nunca_vira_sucesso(armazem) -> None:
    aberta = _linha(armazem, status="started")
    _linha(armazem)                                     # um build integral depois dela não basta
    assert _estado(armazem) == ("not_verified", "open_execution")
    assert governance.abandonar(armazem, aberta) == 1
    assert governance.abandonar(armazem, aberta) == 0   # só linha aberta se abandona
    assert _estado(armazem) == ("not_verified", "overlapping_execution")    # abandonada depois de o build começar
    _linha(armazem)
    assert _estado(armazem) == ("verified", None)
    with armazem.connect() as conexao:
        assert conexao.execute(text(f"select status from {governance.LOG} where invocation_id = :i"),
                               {"i": aberta}).scalar() == "abandoned"


@pytest.mark.integracao
def test_a_ordem_e_a_da_sequence_e_nao_a_do_relogio(armazem) -> None:
    """A última execução é a de maior `sequence`, mesmo com um `started_at` mais antigo."""
    _linha(armazem)
    parcial = _linha(armazem, full_build=False)
    with armazem.begin() as conexao:
        conexao.execute(text(f"update {governance.LOG} set started_at = started_at - interval '1 day', "
                             "finished_at = finished_at - interval '1 day' where invocation_id = :i"), {"i": parcial})
    assert _estado(armazem) == ("not_verified", "partial_execution")


@pytest.mark.integracao
def test_a_execucao_sobreposta_tira_o_verified(armazem) -> None:
    antiga = _linha(armazem)
    _linha(armazem)
    with armazem.begin() as conexao:                    # a anterior terminou depois de a última começar
        conexao.execute(text(f"update {governance.LOG} set finished_at = clock_timestamp() + interval '1 hour' "
                             "where invocation_id = :i"), {"i": antiga})
    assert _estado(armazem) == ("not_verified", "overlapping_execution")


@pytest.mark.integracao
def test_a_mutacao_fora_do_dbt_abre_antes_e_fecha_depois(armazem) -> None:
    _linha(armazem)
    with governance.registrar_mutacao(armazem, "drop_snapshots", {}) as invocacao:
        assert _estado(armazem) == ("not_verified", "open_execution")           # aberta durante a escrita
    assert _estado(armazem) == ("not_verified", "partial_execution")            # fechada, e parcial
    with pytest.raises(RuntimeError):
        with governance.registrar_mutacao(armazem, "test_fato", {}):
            raise RuntimeError("a escrita falhou")
    assert _estado(armazem) == ("not_verified", "failed_execution")
    with armazem.connect() as conexao:
        assert conexao.execute(text(f"select command, full_build from {governance.LOG} where invocation_id = :i"),
                               {"i": invocacao}).one() == ("drop_snapshots", False)


@pytest.mark.integracao
def test_o_estado_e_o_fecho_sao_coerentes_no_banco(armazem) -> None:
    with pytest.raises(Exception, match="ck_dbt_invocations_fecho"):
        with armazem.begin() as conexao:
            conexao.execute(text(f"insert into {governance.LOG} (invocation_id, command, status, finished_at) "
                                 "values ('x', 'build', 'started', clock_timestamp())"))
    with pytest.raises(Exception, match="ck_dbt_invocations_commit"):
        _linha(armazem, git_commit="abc")


@pytest.mark.integracao
def test_a_confirmacao_dos_insumos_so_vale_com_tudo_igual(armazem) -> None:
    invocacao = _linha(armazem, inputs_confirmed=False)
    antes = (COMMIT, "false", "d1")
    assert governance.confirmar_insumos(armazem, invocacao, antes, (COMMIT, "false", "d2")) == "mudaram"
    assert _estado(armazem) == ("not_verified", "inputs_not_confirmed")
    assert governance.confirmar_insumos(armazem, "outra", antes, antes) == "sem_linha"
    assert governance.confirmar_insumos(armazem, invocacao, antes, antes) == "confirmados"
    assert _estado(armazem) == ("verified", None)


@pytest.mark.integracao
def test_o_transformer_insere_so_com_insert_porque_a_sequence_e_identidade(armazem) -> None:
    """RVL5-2-05, medido: sem *grant* de sequência, o `insert` com o padrão da identidade passa."""
    with armazem.begin() as conexao:
        conexao.execute(text(f"grant usage on schema {governance.SCHEMA} to transformer"))
        conexao.execute(text(f"grant insert, update, select on {governance.LOG} to transformer"))
        conexao.execute(text("set local role transformer"))
        conexao.execute(text(f"insert into {governance.LOG} (invocation_id, command) values ('pelo-transformer', 'run')"))
