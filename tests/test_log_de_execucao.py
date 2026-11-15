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
import pathlib
import subprocess
import uuid

import pytest
from sqlalchemy import create_engine, text

from mvp_ed1 import governance
from mvp_ed1.db import WAREHOUSE, database_url
from mvp_ed1.models import pacote

COMMIT = "a" * 40


# ── Sem banco ────────────────────────────────────────────────────────────────────


def _fecho(resultados: list[tuple[str, str]], comando: str = "build", vazio: bool = False) -> str:
    """Renderiza a macro **real** `registrar_fecho` sobre um grafo sintético, com o Jinja do dbt.

    Só o `_escreve_o_armazem()` é trocado por uma variável: o `return()` dele é do dbt, não do Jinja."""
    import json
    import types

    import jinja2

    fonte = (pathlib.Path(__file__).resolve().parents[1] / "dbt" / "macros" / "log_de_execucao.sql").read_text(
        encoding="utf-8")
    assert fonte.count("{%- if _escreve_o_armazem() -%}") == 2
    fonte = fonte.replace("{%- if _escreve_o_armazem() -%}", "{%- if escreve -%}")
    no = lambda uid, tipo: {"unique_id": uid, "resource_type": tipo}           # noqa: E731
    grafo = {"nodes": {u: no(u, tipo) for u, tipo in (("model.p.m", "model"), ("seed.p.s", "seed"),
                                                     ("test.p.t", "test"), ("operation.p.h", "operation"))},
             "unit_tests": {"unit_test.p.m.u": no("unit_test.p.m.u", "unit_test")}}
    ambiente = jinja2.Environment(extensions=["jinja2.ext.do"])
    modulo = ambiente.from_string(fonte).make_module({
        "escreve": True, "graph": grafo, "invocation_id": "i", "tojson": json.dumps,
        "flags": types.SimpleNamespace(WHICH=comando, EMPTY=vazio)})
    return str(modulo.registrar_fecho([types.SimpleNamespace(status=s, node=types.SimpleNamespace(unique_id=u))
                                       for u, s in resultados]))


def test_o_fecho_exige_tambem_os_testes_de_unidade_do_grafo() -> None:
    """RVL5I-1-01: `--exclude-resource-type unit_test` executa tudo menos as unidades — não é integral."""
    todos = [("model.p.m", "success"), ("seed.p.s", "success"), ("test.p.t", "pass"), ("unit_test.p.m.u", "pass")]
    assert "full_build = true" in _fecho(todos)
    assert "full_build = false" in _fecho([r for r in todos if not r[0].startswith("unit_test.")])
    assert "full_build = false" in _fecho([r for r in todos if r[0] != "test.p.t"])
    assert "full_build = false" in _fecho(todos, comando="run")
    assert "full_build = false" in _fecho(todos, vazio=True)
    assert "full_build = false" in _fecho([(u, "reused" if u == "model.p.m" else s) for u, s in todos])
    falhou = _fecho([(u, "fail" if u == "unit_test.p.m.u" else s) for u, s in todos])
    assert "status = 'failed'" in falhou and "full_build = true" in falhou


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


@pytest.mark.integracao
def test_a_sincronizacao_do_airbyte_abre_antes_do_post_e_fecha_no_estado_terminal(armazem, monkeypatch) -> None:
    """RVL5-5-02: o `drop_cascade` do destino derruba views de `staging`; a sincronização é escrita registrada."""
    from mvp_ed1 import airbyte

    monkeypatch.setattr(airbyte, "_armazem", lambda: armazem)
    _linha(armazem)
    vistos: list[tuple] = []

    def chamar(caminho, _jwt, corpo=None):
        if caminho == "/jobs":
            vistos.append(_estado(armazem))                         # o POST vê a linha já aberta
            return {"jobId": 77}
        return {"status": "succeeded", "rowsSynced": 1}
    monkeypatch.setattr(airbyte, "_chamar", chamar)
    monkeypatch.setattr(airbyte.time, "sleep", lambda _s: None)

    assert airbyte.sincronizar("conexao", "jwt")["jobId"] == 77
    assert vistos == [("not_verified", "open_execution")]
    assert _estado(armazem) == ("not_verified", "open_execution")          # quem espera ainda não viu o fim
    airbyte.acompanhar(77, "jwt", intervalo=0)
    assert _estado(armazem) == ("not_verified", "partial_execution")       # fechada, e mais nova que o build

    def post_recusado(caminho, _jwt, corpo=None):
        raise airbyte.AirbyteIndisponivel("400 em /jobs", recusado=True)
    monkeypatch.setattr(airbyte, "_chamar", post_recusado)
    with pytest.raises(airbyte.AirbyteIndisponivel):
        airbyte.sincronizar("conexao", "jwt")
    assert _estado(armazem) == ("not_verified", "failed_execution")     # recusa provada: nada foi criado
    with armazem.connect() as conexao:
        assert conexao.execute(text(f"select job_id, status from {governance.LOG} where command = 'airbyte_sync' "
                                    "order by sequence")).all() == [(77, "success"), (None, "failed")]


@pytest.mark.integracao
@pytest.mark.parametrize("falha", [TimeoutError("resposta perdida"), KeyboardInterrupt(),
                                   "503", "sem jobId"])
def test_o_post_sem_prova_de_recusa_deixa_a_linha_aberta(armazem, monkeypatch, falha) -> None:
    """RVL5I-1-02: o servidor pode ter aceitado o *job* e a resposta se perdido; a linha fechada seria superada
    pelo *build* seguinte enquanto o *job* derruba o que ele construiu. Fica aberta, e o *build* não verifica."""
    from mvp_ed1 import airbyte

    monkeypatch.setattr(airbyte, "_armazem", lambda: armazem)

    def chamar(caminho, _jwt, corpo=None):
        if falha == "503":
            raise airbyte.AirbyteIndisponivel("503 em /jobs")
        if falha == "sem jobId":
            return {}
        raise falha
    monkeypatch.setattr(airbyte, "_chamar", chamar)
    with pytest.raises(BaseException):
        airbyte.sincronizar("conexao", "jwt")
    assert _estado(armazem) == ("not_verified", "open_execution")
    _linha(armazem)                                     # o build limpo depois não passa por cima
    assert _estado(armazem) == ("not_verified", "open_execution")


def test_so_o_4xx_e_a_conexao_recusada_provam_que_nada_foi_criado(monkeypatch) -> None:
    """A classificação do `_chamar`, com o transporte substituído: o resto não prova recusa (RVL5I-1-02)."""
    import io
    import urllib.error

    from mvp_ed1 import airbyte

    for erro, recusado in ((urllib.error.HTTPError("u", 400, "x", {}, io.BytesIO(b"")), True),
                           (urllib.error.HTTPError("u", 422, "x", {}, io.BytesIO(b"")), True),
                           (urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b"")), False),
                           (urllib.error.HTTPError("u", 504, "x", {}, io.BytesIO(b"")), False),
                           (urllib.error.URLError(ConnectionRefusedError(111, "recusada")), True),
                           (urllib.error.URLError(TimeoutError("timed out")), False)):
        def abrir(_req, timeout, erro=erro):
            raise erro
        monkeypatch.setattr(airbyte.urllib.request, "urlopen", abrir)
        with pytest.raises(airbyte.AirbyteIndisponivel) as pego:
            airbyte._chamar("/jobs", "jwt", {"a": 1})
        assert pego.value.recusado is recusado, erro


@pytest.mark.integracao
def test_a_primeira_sincronizacao_prepara_o_log_antes_do_post(armazem, monkeypatch) -> None:
    """RVL5I-1-03: na instalação nova, a sincronização vem antes do primeiro *build* e do legado."""
    from mvp_ed1 import airbyte

    with armazem.begin() as conexao:
        conexao.execute(text(f"drop schema {governance.SCHEMA} cascade"))
    monkeypatch.setattr(airbyte, "_armazem", lambda: armazem)
    vistos = []
    monkeypatch.setattr(airbyte, "_chamar", lambda caminho, _jwt, corpo=None: vistos.append(_estado(armazem))
                        or {"jobId": 5})
    assert airbyte.sincronizar("conexao", "jwt")["jobId"] == 5
    assert vistos == [("not_verified", "open_execution")]


@pytest.mark.integracao
def test_a_restauracao_da_memoria_conclui_e_preserva_o_log_e_a_ordem(armazem, tmp_path) -> None:
    """RVL5-5-01, RVL5-6-01: os mesmos `_pg_dump` e `_pg_restore` da recuperação, num armazém efêmero. O
    arquivo "antigo" traz o log dentro (sem a exclusão); a restauração conclui, não o substitui, a linha que a
    registra sobrevive e a `sequence` continua a do armazém. Interrompida antes do *rebuild*: não verificado."""
    from mvp_ed1.recovery import cli

    banco, usuario = os.environ["WAREHOUSE_DB_NAME"], os.environ["WAREHOUSE_DB_USER"]
    antiga = _linha(armazem)
    with armazem.begin() as conexao:                       # um certificado qualquer, para ver o resto voltar
        conexao.execute(text(f"insert into {governance.SCHEMA}.legacy_captures (capture_attempt_id, source_table, "
                             "connection_name, source_rows_before, source_hash_before, status, started_at) "
                             "values ('t1', 'brands', 'c', 1, 'h', 'complete', clock_timestamp())"))
    arquivo = tmp_path / "memoria_antiga.dump"
    original = cli.pacote.FORA_DA_MEMORIA
    try:                                                   # o arquivo antigo: sem a exclusão do log
        cli.pacote.FORA_DA_MEMORIA = ()
        cli._pg_dump("warehouse_db", usuario, banco, arquivo, ("governance",))
    finally:
        cli.pacote.FORA_DA_MEMORIA = original
    with armazem.begin() as conexao:
        conexao.execute(text(f"delete from {governance.SCHEMA}.legacy_captures"))
    nova = _linha(armazem)                                 # um build depois do arquivo

    with governance.registrar_mutacao(armazem, "recovery_restore") as restauracao:
        cli._pg_restore("warehouse_db", usuario, banco, arquivo)

    with armazem.connect() as conexao:
        log = conexao.execute(text(f"select invocation_id, sequence from {governance.LOG} order by sequence")).all()
        certificados = conexao.execute(text(f"select count(*) from {governance.SCHEMA}.legacy_captures")).scalar_one()
    assert [i for i, _ in log] == [antiga, nova, restauracao]           # o log não voltou ao do arquivo
    assert [s for _, s in log] == sorted(s for _, s in log) and len({s for _, s in log}) == 3
    assert certificados == 1                                             # o resto de `governance` voltou
    assert _estado(armazem) == ("not_verified", "partial_execution")     # interrompida antes do rebuild
    _linha(armazem)
    with armazem.connect() as conexao:                                   # a identidade continua a do armazém
        assert conexao.execute(text(f"select max(sequence) from {governance.LOG}")).scalar_one() == log[-1][1] + 1
