"""Nenhum escritor novo das camadas construídas entra calado (ADR-0054, RVL5-4-01, RVL5-5-03).

A procedência do armazém só vale se **toda** escrita suportada fora do dbt se registra no log de execução
(`governance.registrar_mutacao`). Este teste varre o código atrás de escrita SQL nas camadas que o dbt
constrói, de `pg_restore` e de disparo do Airbyte, e exige que cada arquivo esteja na lista declarada,
com o motivo — e que a lista não guarde arquivo que já não escreve.

**O alcance é lexical, e declarado:** SQL montado em tempo de execução (um `insert into {FATO}`) não é
visto, e por isso os escritores conhecidos fora do alcance estão listados à parte; uma escrita nova num
arquivo **já** listado depende da revisão da mudança, não desta guarda.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CAMADAS = r"(staging|trusted|analytics|consumption|quarantine|snapshots)"
ESCRITA = re.compile(
    r"(?i)\b(?:insert\s+into|update|delete\s+from|truncate(?:\s+table)?|drop\s+(?:schema|table|view|materialized\s+view)"
    r"|alter\s+table|create\s+(?:or\s+replace\s+)?(?:table|view|materialized\s+view|schema))"
    r"\s+(?:if\s+(?:not\s+)?exists\s+)?[\"'`]?" + CAMADAS + r"\b")
RESTAURACAO = re.compile(r"[\"']pg_restore[\"']")
DISPARO = re.compile(r"[\"']/jobs[\"']\s*,\s*\w+\s*,\s*\{")
ONDE = ("src", "tests", "Makefile", "docker", "airflow")

#: Cada arquivo que a varredura acha, e por que ele pode escrever.
DECLARADOS: dict[str, str] = {
    "src/mvp_ed1/governance.py": "o descarte dos snapshots, por `registrar_mutacao('drop_snapshots')`",
    "src/mvp_ed1/recovery/cli.py": "a restauração da memória, por `registrar_mutacao('recovery_restore')`",
    "src/mvp_ed1/airbyte.py": "o funil dos disparos: `sincronizar` registra `airbyte_sync` antes do POST",
    "tests/test_recovery.py": "testes de unidade com o `pg_restore` substituído; não tocam banco",
    "tests/test_legado_remocao.py": "escreve em bancos efêmeros, não no armazém de trabalho",
    "tests/test_oraculo_da_memoria.py": "escreve em bancos efêmeros, não no armazém de trabalho",
}

#: Escritores conhecidos que a varredura **não** vê (SQL montado em tempo de execução).
FORA_DO_ALCANCE: dict[str, str] = {
    "tests/test_fato_incremental.py": "adultera `{FATO}` com `make test FATO=1`, por `registrar_mutacao('test_fato')`",
}


def _o_que_escreve(texto: str) -> set[str]:
    achado = {f"escrita em {m.group(1).lower()}" for m in ESCRITA.finditer(texto)}
    if RESTAURACAO.search(texto):
        achado.add("pg_restore")
    if DISPARO.search(texto):
        achado.add("disparo do Airbyte")
    return achado


def _varrer() -> dict[str, set[str]]:
    arquivos = subprocess.run(["git", "ls-files", *ONDE], cwd=RAIZ, capture_output=True, text=True,
                              check=True).stdout.split()
    saida = {}
    for relativo in arquivos:
        caminho = RAIZ / relativo
        if caminho == pathlib.Path(__file__).resolve():
            continue                                    # os padrões e as contraprovas deste teste
        if caminho.suffix not in (".py", ".sh", ".sql", ".yml", ".yaml") and caminho.name != "Makefile":
            continue
        if (achado := _o_que_escreve(caminho.read_text(encoding="utf-8", errors="replace"))):
            saida[relativo] = achado
    return saida


def test_todo_escritor_das_camadas_construidas_esta_declarado() -> None:
    achados = _varrer()
    assert sorted(set(achados) - set(DECLARADOS)) == [], (
        "escritor novo das camadas construídas fora da lista: registre a escrita em `governance.registrar_mutacao` "
        f"(ADR-0054) e declare-o aqui, com o motivo — {[(a, sorted(achados[a])) for a in set(achados) - set(DECLARADOS)]}")
    assert sorted(set(DECLARADOS) - set(achados)) == [], "declarado que já não escreve: tire da lista"


def test_os_de_fora_do_alcance_registram_a_escrita() -> None:
    for relativo in FORA_DO_ALCANCE:
        texto = (RAIZ / relativo).read_text(encoding="utf-8")
        assert "registrar_mutacao(" in texto, relativo
        assert not _o_que_escreve(texto), f"{relativo} passou a ser visto: mova-o para DECLARADOS"


def test_a_guarda_pega_o_escritor_novo_inclusive_a_view_substituida() -> None:
    """A contraprova: cada forma que o desenho promete pegar, num arquivo novo, é achada."""
    for texto in ('conexao.execute(text("insert into analytics.fact_x values (1)"))',
                  "update trusted.orders set x = 1",
                  "DELETE FROM quarantine.rejected_x",
                  "truncate table snapshots.scd_product",
                  "drop view if exists consumption.v_x",
                  "alter table staging.stg_x add column y int",
                  "create or replace view consumption.monthly_x as select 1",
                  "create table trusted.copia as select * from trusted.orders",
                  'subprocess.run(["pg_restore", "-d", "warehouse"])',
                  '_chamar("/jobs", jwt, {"connectionId": c, "jobType": "sync"})'):
        assert _o_que_escreve(texto), texto
    for inocente in ("select * from analytics.fact_x", "from {{ ref('stg_x') }}", "update dos documentos",
                     'listagem = {"jobType": "sync"}', "create table raw.x (a int)"):
        assert not _o_que_escreve(inocente), inocente
