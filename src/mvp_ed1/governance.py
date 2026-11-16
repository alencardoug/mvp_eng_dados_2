"""O schema `governance` do armazém — DDL versionado, idempotente e com teste.

O [ADR-0023] declarou o schema e fechou o seu escopo em quatro conjuntos; o
[ADR-0044] materializa a primeira tabela do conjunto "log de execução":
`legacy_captures`, o certificado por *stream* de cada captura do legado. O
armazém não tem Alembic (o ADR-0010 não o exige ali), então o ciclo de vida
destas tabelas vive aqui: uma lista **ordenada** de migrações, cada uma
idempotente, aplicadas por `garantir()` e registradas em `governance._versions`.
Acrescentar coluna é acrescentar uma migração à lista — nunca editar a anterior.

Os papéis de acesso do [ADR-0011] nascem aqui pela mesma razão: são objetos do
*cluster*, não do dbt, e um `init` do contêiner só roda com o volume vazio — um
armazém já povoado nunca os receberia. `garantir()` os cria se faltarem, a cada
execução, no ambiente novo e no existente. O que cada papel alcança não está
aqui: é declarado camada a camada no dbt (`+grants`, `meta.writers`,
`meta.grants`) e aplicado ao fim de cada execução
(`macros/aplicar_acesso_por_camada.sql`).

O **login de leitura** nasce aqui pela mesma razão (N4 do plano do
`bi-como-codigo`, v1.1.0): o primeiro consumidor que se conecta como membro do
próprio papel, em vez do superusuário. Ver `_garantir_leitor`.

Se a Etapa 11 decidir levar o armazém para o Alembic, esta lista é o que vira
histórico; até lá, é o que impede DDL solto.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import os
import re
import secrets
import uuid

from sqlalchemy import Engine, text

SCHEMA = "governance"

#: Papéis de acesso (ADR-0011, Governança §7), na ordem da tabela. São grupos de
#: privilégio **sem login**: quem se conecta é membro de um deles — hoje o único
#: login do armazém é o superusuário do `.env`, que os assume por `set role`.
#: Sem login não há senha nova no `.env`, e o equivalente na fase GCP é o mesmo:
#: grupo IAM ou conta de serviço, nunca uma credencial por papel.
PAPEIS: tuple[str, ...] = ("ingestor", "transformer", "streamer", "analyst", "auditor")

_DESCRICAO_DOS_PAPEIS: dict[str, str] = {
    "ingestor": "Escreve raw e raw_legacy (Airbyte) e o certificado de captura em governance; lê só o que é seu.",
    "transformer": "Escreve staging, trusted, analytics, consumption, quarantine e snapshots (dbt); lê as camadas anteriores.",
    "streamer": "Escreve raw.inventory_movements_stream (Beam, ADR-0031); nada mais.",
    "analyst": "Lê consumption, e só consumption — o contrato de consumo é a view (ADR-0008).",
    "auditor": "Lê quarantine e governance; não escreve.",
}

#: Variáveis do `.env` com o login de leitura. O banco, a porta e o host são os
#: do armazém (`WAREHOUSE_DB_*`): muda só quem se conecta.
LEITOR_USUARIO = "WAREHOUSE_READER_USER"
LEITOR_SENHA = "WAREHOUSE_READER_PASSWORD"

#: O papel do leitor — e o único. Membro de `analyst`, ele lê o que `analyst` lê.
PAPEL_DO_LEITOR = "analyst"

#: Conferidos com `fullmatch`: `$` com `match` aceitava um `\n` no fim (RVL2-02).
_NOME = re.compile(r"[a-z_][a-z0-9_]{0,62}")
#: A forma que `make env` gera. Mais estreita que o necessário de propósito: a
#: senha nunca precisa de escape, e uma senha curta ou estranha é recusada.
_SENHA = re.compile(r"[A-Za-z0-9]{24,}")

#: Funções do `pg_catalog` que o PostgreSQL deixa a `PUBLIC` e que fazem um
#: login sem nenhum grant escrever ou interferir (RVL2-01, revisão do lote 2 da
#: v1.1.0): os *large objects* ficam fora dos grants de tabela — o leitor os
#: criava pedindo `read write` —, e os *advisory locks* são os mesmos com que a
#: captura marca chamador vivo (`legacy.captura.bloqueio_da_tentativa`): um
#: leitor que tomasse o de uma tentativa a deixaria pendente para sempre.
#: `pg_logical_emit_message` grava mensagem no WAL, e com `transactional=false`
#: ela fica mesmo com *rollback* (RVL2-2-01). Toda assinatura de cada nome sai de
#: `PUBLIC`; o superusuário, que é quem captura, carrega e transforma, não depende
#: de `EXECUTE`. Ler um *large object* e soltar um lock ficam: sem criar nem
#: tomar, não há o que ler nem o que soltar. O que continua aberto ao leitor, e
#: por quê, está fixado em `tests/test_acesso.py` (`ABERTAS_AO_LEITOR`), com o
#: recorte declarado lá: um nome volátil novo numa versão do PostgreSQL faz o
#: teste falhar até ser classificado.
FECHADAS_A_PUBLIC: tuple[str, ...] = (
    "lo_creat", "lo_create", "lo_from_bytea", "lo_open", "lo_put", "lowrite",
    "lo_truncate", "lo_truncate64", "lo_unlink",
    "pg_advisory_lock", "pg_advisory_lock_shared", "pg_advisory_xact_lock", "pg_advisory_xact_lock_shared",
    "pg_try_advisory_lock", "pg_try_advisory_lock_shared", "pg_try_advisory_xact_lock",
    "pg_try_advisory_xact_lock_shared",
    "pg_logical_emit_message",
)

#: Migrações em ordem: (nome, comandos). Cada comando é idempotente por si.
MIGRACOES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "0001_legacy_captures",
        (
            f"create schema if not exists {SCHEMA}",
            f"""
            create table if not exists {SCHEMA}.legacy_captures (
                capture_attempt_id   text        not null,
                source_table         text        not null,
                connection_name      text        not null,
                job_id               bigint,
                snapshot_id          bigint,
                source_rows_before   integer     not null,
                source_hash_before   text        not null,
                source_rows_after    integer,
                source_hash_after    text,
                received_rows        integer,
                received_hash        text,
                sync_id_matches      boolean,
                status               text        not null,
                started_at           timestamptz not null,
                completed_at         timestamptz,
                primary key (capture_attempt_id, source_table),
                constraint ck_legacy_captures_status check (
                    status in ('pending', 'complete', 'unstable', 'incomplete', 'inconsistent', 'abandoned')
                )
            )
            """,
            f"""
            comment on table {SCHEMA}.legacy_captures is
            'Certificado por stream de cada captura do legado (ADR-0044): origem antes e depois do job, bruto recebido, vínculo com o job. Lido pelo fluxo só para elegibilidade.'
            """,
            f"create index if not exists ix_legacy_captures_snapshot on {SCHEMA}.legacy_captures (snapshot_id, status)",
        ),
    ),
    (
        # A identidade da captura passou a ser o job (`schema.CAPTURA_SQL`),
        # não a geração do Airbyte, que é por stream. Os certificados já
        # gravados carregavam a geração; passam a carregar o job — o mesmo
        # dado que já estava em `job_id`.
        "0002_snapshot_id_e_o_job",
        (
            f"update {SCHEMA}.legacy_captures set snapshot_id = job_id where job_id is not null",
            f"comment on column {SCHEMA}.legacy_captures.snapshot_id is "
            "'Identidade da captura = job de sincronização (_airbyte_meta.sync_id); desde 15/09/2026, não a geração, que é por stream.'",
        ),
    ),
    (
        # O log de execução da ADR-0023 materializado para o dbt e para as escritas do armazém fora
        # dele (ADR-0054): duas fases por linha, como `legacy_captures`.
        "0003_dbt_invocations",
        (
            f"""
            create table if not exists {SCHEMA}.dbt_invocations (
                sequence             bigint      not null generated always as identity primary key,
                invocation_id        text        not null unique,
                command              text        not null,
                git_commit           text,
                git_tree_dirty       boolean,
                inputs_confirmed     boolean     not null default false,
                dbt_version          text,
                target               text,
                started_at           timestamptz not null default clock_timestamp(),
                finished_at          timestamptz,
                abandoned_at         timestamptz,
                full_build           boolean,
                status               text        not null default 'started',
                result_counts        jsonb,
                job_id               bigint,
                constraint ck_dbt_invocations_status check (status in ('started', 'success', 'failed', 'abandoned')),
                constraint ck_dbt_invocations_commit check (git_commit is null or git_commit ~ '^[0-9a-f]{{40}}$'),
                constraint ck_dbt_invocations_fecho check (
                    (status = 'started' and finished_at is null and abandoned_at is null)
                    or (status in ('success', 'failed') and finished_at is not null and abandoned_at is null)
                    or (status = 'abandoned' and abandoned_at is not null and finished_at is null)
                )
            )
            """,
            f"""
            comment on table {SCHEMA}.dbt_invocations is
            'Log de execução (ADR-0023, ADR-0054): cada execução do dbt que escreve o armazém e cada escrita suportada fora dele, em duas fases — aberta antes de escrever, fechada no fim. Linha aberta bloqueia a procedência.'
            """,
            f"""
            create or replace view {SCHEMA}.warehouse_provenance as
            with ultima as (
                select * from {SCHEMA}.dbt_invocations order by sequence desc limit 1
            ), abertas as (
                select count(*) as n from {SCHEMA}.dbt_invocations where status = 'started'
            ), sobrepostas as (
                select count(*) as n from {SCHEMA}.dbt_invocations i, ultima u
                where i.sequence < u.sequence and coalesce(i.finished_at, i.abandoned_at) >= u.started_at
            ), motivo as (
                select u.*, case
                    when u.sequence is null then 'no_execution'
                    when a.n > 0 then 'open_execution'
                    when u.status = 'abandoned' then 'abandoned_execution'
                    when u.status <> 'success' then 'failed_execution'
                    when u.full_build is not true then 'partial_execution'
                    when u.git_commit is null then 'unknown_commit'
                    when u.git_tree_dirty is not false then 'dirty_tree'
                    when not u.inputs_confirmed then 'inputs_not_confirmed'
                    when s.n > 0 then 'overlapping_execution'
                end as reason
                from (select 1) as x left join ultima u on true cross join abertas a cross join sobrepostas s
            )
            select case when reason is null then 'verified' else 'not_verified' end as status,
                   reason,
                   invocation_id,
                   git_commit                as built_from_commit,
                   finished_at               as built_at,
                   sequence
            from motivo
            """,
            f"""
            comment on view {SCHEMA}.warehouse_provenance is
            'A procedência do armazém (ADR-0054): verified só quando a última execução é um build integral, aprovado, de commit conhecido e limpo, com os insumos confirmados, sem nada aberto nem sobreposto; senão not_verified, com o motivo.'
            """,
        ),
    ),
    (
        # Uma invocação de `analytics` de cada vez (ADR-0056, Q38). A abertura grava o escopo quando a
        # invocação reconstrói `analytics` (o predicado das chaves, `macros/chaves.sql`), e o índice
        # parcial torna a admissão atômica: a segunda abertura com o escopo, enquanto a primeira está
        # aberta, viola o índice e é recusada. As capturas, as mutações fora do dbt, o `seed` e o
        # `snapshot` gravam nulo e seguem como antes. A linha aberta só sai pelo fecho ou pelo abandono.
        "0004_escopo_exclusivo",
        (
            f"""
            alter table {SCHEMA}.dbt_invocations add column if not exists exclusive_scope text
                constraint ck_dbt_invocations_scope check (exclusive_scope is null or exclusive_scope = 'analytics')
            """,
            f"""
            create unique index if not exists ux_dbt_invocations_open_scope on {SCHEMA}.dbt_invocations (exclusive_scope)
                where status = 'started' and exclusive_scope is not null
            """,
            f"""
            comment on column {SCHEMA}.dbt_invocations.exclusive_scope is
            'O escopo que admite uma invocação de cada vez (ADR-0056): analytics na que reconstrói analytics; nulo nas demais.'
            """,
        ),
    ),
)

#: O que a regra de leitura pode responder, na ordem em que a *view* testa (ADR-0054).
MOTIVOS = ("no_execution", "open_execution", "abandoned_execution", "failed_execution", "partial_execution",
           "unknown_commit", "dirty_tree", "inputs_not_confirmed", "overlapping_execution")
LOG = f"{SCHEMA}.dbt_invocations"
PROCEDENCIA = f"{SCHEMA}.warehouse_provenance"


def _garantir_papeis(conexao) -> None:
    """Cria os papéis que faltam. Não é migração de propósito: migração roda uma
    vez, e um papel apagado à mão só voltaria com outra migração; aqui ele volta
    na execução seguinte. `create role` não tem `if not exists` — o bloco `do`
    faz as vezes. Os papéis são criados, nunca alterados nem apagados por aqui;
    o que cada um alcança é assunto do dbt (ver docstring do módulo)."""
    for papel in PAPEIS:
        conexao.execute(
            text(
                f"""
                do $$
                begin
                    if not exists (select from pg_roles where rolname = '{papel}') then
                        create role {papel} nologin;
                    end if;
                end
                $$
                """
            )
        )
        conexao.execute(text(f"comment on role {papel} is '{_DESCRICAO_DOS_PAPEIS[papel]}'"))


def _verificador_scram(senha: str, iteracoes: int = 4096) -> str:
    """O verificador SCRAM-SHA-256 da senha, calculado aqui (RFC 5802, RFC 7677).

    É o que o PostgreSQL guarda de qualquer forma; mandá-lo pronto faz a senha
    em texto nunca chegar ao servidor — nem a um log de comandos, se alguém o
    ligar. É o que o `\\password` do `psql` faz. A normalização SASLprep do RFC
    não muda nada aqui: `_SENHA` só aceita ASCII alfanumérico."""
    sal = secrets.token_bytes(16)
    salgada = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, iteracoes)
    cliente = hmac.new(salgada, b"Client Key", hashlib.sha256).digest()
    servidor = hmac.new(salgada, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"SCRAM-SHA-256${iteracoes}:{b64(sal)}${b64(hashlib.sha256(cliente).digest())}:{b64(servidor)}"


def leitor_do_ambiente(ambiente: dict[str, str] | None = None) -> tuple[str, str] | None:
    """`(usuário, senha)` do login de leitura, ou `None` se o `.env` não o declara."""
    ambiente = os.environ if ambiente is None else ambiente
    usuario, senha = ambiente.get(LEITOR_USUARIO), ambiente.get(LEITOR_SENHA)
    if not usuario and not senha:
        return None
    if not usuario or not senha:
        raise RuntimeError(f"defina {LEITOR_USUARIO} e {LEITOR_SENHA} juntos no .env, ou nenhum dos dois")
    if not _NOME.fullmatch(usuario) or usuario in PAPEIS or usuario == ambiente.get("WAREHOUSE_DB_USER"):
        raise RuntimeError(f"{LEITOR_USUARIO} inválido: um nome novo, minúsculo, que não seja papel nem o superusuário")
    if not _SENHA.fullmatch(senha):
        raise RuntimeError(f"{LEITOR_SENHA} fora da forma de `make env`: 24 ou mais letras e dígitos")
    return usuario, senha


def _garantir_leitor(conexao, usuario: str, senha: str) -> None:
    """O login de leitura, inteiro, a cada execução — como os papéis.

    Membro de `analyst` e de nada mais, sem `admin option`; sem nenhum dos
    atributos que escalam (`superuser`, `createdb`, `createrole`, `replication`,
    `bypassrls`); leitura como padrão da sessão, e nenhum outro padrão — nem o
    global nem o de banco nenhum; e a senha do `.env`, reposta a
    cada vez, para que o `.env` seja sempre a verdade. O que já estiver diferente
    é desfeito — o mesmo princípio do `on-run-end`, que revoga o não declarado.

    E `temporary` sai de `PUBLIC` no banco, com as funções de `FECHADAS_A_PUBLIC`:
    sem isso, todo login cria tabela temporária e *large object* e toma os locks
    da captura, e "não escreve" teria exceções. Os demais logins são o
    superusuário, a quem a revogação não alcança.

    O que vem do catálogo — os papéis de que o login é membro, o nome do banco,
    as assinaturas das funções — se compõe no servidor, com `format('%I')`, e
    nunca passa por texto Python (RVL2-02). O que vem do `.env` já chega
    validado por `leitor_do_ambiente`."""
    conexao.execute(text(
        f"""
        do $$
        begin
            if not exists (select from pg_roles where rolname = '{usuario}') then
                create role {usuario} login;
            end if;
        end
        $$
        """
    ))
    # `exec_driver_sql`, e não `text()`: os `:` do verificador virariam parâmetros.
    # Na falha, o comando não sobe com o erro — ele leva o verificador.
    try:
        conexao.exec_driver_sql(
            f"alter role {usuario} with login inherit nosuperuser nocreatedb nocreaterole noreplication "
            f"nobypassrls password '{_verificador_scram(senha)}'"
        )
    except Exception as erro:
        raise RuntimeError(f"não foi possível definir o login {usuario}: {type(erro.__cause__ or erro).__name__}") from None
    # Todo padrão do papel volta ao declarado, o global e o de cada banco: o leitor
    # pode `alter role … [in database …] set` sobre si mesmo, e o padrão por banco
    # vence o global — repor só o global deixava o dele valendo (RVL2-3-07).
    conexao.execute(text(
        f"""
        do $$
        declare r record;
        begin
            for r in select d.datname from pg_db_role_setting s join pg_database d on d.oid = s.setdatabase
                     where s.setrole = '{usuario}'::regrole loop
                execute format('alter role %I in database %I reset all', '{usuario}', r.datname);
            end loop;
        end
        $$
        """
    ))
    conexao.execute(text(f"alter role {usuario} reset all"))
    conexao.execute(text(f"alter role {usuario} set default_transaction_read_only = on"))
    conexao.execute(text(
        f"""
        do $$
        declare r record;
        begin
            for r in select g.rolname from pg_auth_members m join pg_roles g on g.oid = m.roleid
                     join pg_roles u on u.oid = m.member
                     where u.rolname = '{usuario}' and g.rolname <> '{PAPEL_DO_LEITOR}' loop
                execute format('revoke %I from %I', r.rolname, '{usuario}');
            end loop;
        end
        $$
        """
    ))
    conexao.execute(text(f"revoke admin option for {PAPEL_DO_LEITOR} from {usuario}"))
    conexao.execute(text(f"grant {PAPEL_DO_LEITOR} to {usuario}"))
    conexao.execute(text(f"comment on role {usuario} is 'Login só de leitura, membro de {PAPEL_DO_LEITOR}: o consumidor de fora do armazém (v1.1.0).'"))
    _fechar_a_public(conexao)


def _fechar_a_public(conexao) -> None:
    """`temporary` no banco e `EXECUTE` em cada assinatura de `FECHADAS_A_PUBLIC`, tirados de `PUBLIC`.

    Um nome da lista que o `pg_catalog` não tem é erro, não pulo: uma versão do
    PostgreSQL que o renomeasse deixaria o caminho aberto calada."""
    existentes = set(conexao.execute(text(
        "select distinct proname from pg_proc where pronamespace = 'pg_catalog'::regnamespace and proname = any(:n)"
    ), {"n": list(FECHADAS_A_PUBLIC)}).scalars().all())
    if faltam := sorted(set(FECHADAS_A_PUBLIC) - existentes):
        raise RuntimeError(f"funções a fechar que o pg_catalog não tem: {faltam}")
    nomes = ", ".join(f"'{n}'" for n in FECHADAS_A_PUBLIC)
    conexao.execute(text(
        f"""
        do $$
        declare r record;
        begin
            execute format('revoke temporary on database %I from public', current_database());
            for r in select p.oid::regprocedure as f from pg_proc p
                     where p.pronamespace = 'pg_catalog'::regnamespace and p.proname in ({nomes}) loop
                execute format('revoke execute on function %s from public', r.f);
            end loop;
        end
        $$
        """
    ))


#: As mesmas migrações no BigQuery (Etapa 13, G2.1), **com os mesmos nomes**: `_versions` diz,
#: nos dois armazéns, quais delas valem. O que o BigQuery não tem, e para onde foi:
#:
#: - `check (status in …)` → o teste `accepted_values` da fonte (`_legacy__sources.yml`), que roda
#:   nos dois alvos — a regra continua uma só;
#: - `primary key` → declarada `not enforced` (o BigQuery a usa para otimizar, não a impõe); a
#:   unicidade vira o teste de combinação única da fonte, e a escrita do certificado é `MERGE` pela
#:   chave (PLANO_etapa_13 G2.1);
#: - o índice `(snapshot_id, status)` → *clustering* pelas mesmas colunas;
#: - `comment on` → `options(description = …)`.
#:
#: A paridade das colunas (nome, tipo equivalente, nulidade) é conferida por
#: `tests/test_governanca_bigquery.py`, não por leitura.
MIGRACOES_BIGQUERY: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "0001_legacy_captures",
        (
            """
            create table if not exists `{projeto}.{dataset}.legacy_captures` (
                capture_attempt_id   string    not null,
                source_table         string    not null,
                connection_name      string    not null,
                job_id               int64,
                snapshot_id          int64,
                source_rows_before   int64     not null,
                source_hash_before   string    not null,
                source_rows_after    int64,
                source_hash_after    string,
                received_rows        int64,
                received_hash        string,
                sync_id_matches      bool,
                status               string    not null,
                started_at           timestamp not null,
                completed_at         timestamp,
                primary key (capture_attempt_id, source_table) not enforced
            )
            cluster by snapshot_id, status
            options (description = 'Certificado por stream de cada captura do legado (ADR-0044): origem antes e depois do job, bruto recebido, vínculo com o job. Lido pelo fluxo só para elegibilidade.')
            """,
        ),
    ),
    (
        "0002_snapshot_id_e_o_job",
        (
            "update `{projeto}.{dataset}.legacy_captures` set snapshot_id = job_id where job_id is not null",
            "alter table `{projeto}.{dataset}.legacy_captures` alter column snapshot_id set options "
            "(description = 'Identidade da captura = job de sincronização (_airbyte_meta.sync_id); desde 15/09/2026, não a geração, que é por stream.')",
        ),
    ),
    (
        # Só a **tabela**, sem identidade nem `check` (RVL5I-1-06): no BigQuery ainda faltam a view
        # `warehouse_provenance`, um escritor que dê a ordem (os *hooks* de `log_de_execucao.sql` são
        # PostgreSQL: `clock_timestamp()`, `::jsonb`, `commit;`) e o IAM da tabela. A fase GCP está
        # encerrada (Q14); o que falta está nas Pendências, V3, item 10.
        "0003_dbt_invocations",
        (
            """
            create table if not exists `{projeto}.{dataset}.dbt_invocations` (
                sequence             int64     not null,
                invocation_id        string    not null,
                command              string    not null,
                git_commit           string,
                git_tree_dirty       bool,
                inputs_confirmed     bool      not null,
                dbt_version          string,
                target               string,
                started_at           timestamp not null,
                finished_at          timestamp,
                abandoned_at         timestamp,
                full_build           bool,
                status               string    not null,
                result_counts        json,
                job_id               int64,
                primary key (sequence) not enforced
            )
            options (description = 'Log de execução (ADR-0023, ADR-0054): cada execução do dbt que escreve o armazém e cada escrita suportada fora dele, em duas fases.')
            """,
        ),
    ),
    (
        # Só a coluna (ADR-0056): o BigQuery não impõe unicidade, e a admissão atômica lá precisa de outro
        # meio, não desenhado nesta fase.
        "0004_escopo_exclusivo",
        (
            "alter table `{projeto}.{dataset}.dbt_invocations` add column if not exists exclusive_scope string "
            "options (description = 'O escopo que admite uma invocação de cada vez (ADR-0056): analytics na que reconstrói analytics; nulo nas demais.')",
        ),
    ),
)


def garantir_bigquery(cliente, projeto: str, dataset: str = SCHEMA) -> list[str]:
    """`garantir()` no BigQuery: as migrações que faltam, registradas em `_versions`.

    O *dataset* nasce no Terraform (`bigquery.tf`), e os papéis são contas de serviço com IAM
    (`papeis.tf`): aqui só há tabela. Sem transação que envolva DDL no BigQuery, cada migração
    é idempotente por si e só entra em `_versions` depois de todos os comandos dela — uma
    migração interrompida roda de novo inteira na próxima chamada."""
    versoes_ = f"`{projeto}.{dataset}._versions`"
    cliente.query(f"create table if not exists {versoes_} "
                  "(nome string not null, aplicada_em timestamp default current_timestamp() not null)").result()
    feitas = {linha[0] for linha in cliente.query(f"select nome from {versoes_}").result()}
    aplicadas: list[str] = []
    for nome, comandos in MIGRACOES_BIGQUERY:
        if nome in feitas:
            continue
        for comando in comandos:
            cliente.query(comando.format(projeto=projeto, dataset=dataset)).result()
        from google.cloud import bigquery

        cliente.query(f"insert into {versoes_} (nome) values (@n)", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("n", "STRING", nome)])).result()
        aplicadas.append(nome)
    return aplicadas


def versoes_bigquery(armazem) -> list[str]:
    """`versoes()` no BigQuery: as migrações registradas em `_versions`, na mesma ordem."""
    from google.api_core import exceptions as gexc

    try:
        return [linha["nome"] for linha in armazem.linhas(
            f"select nome from {armazem.tabela(SCHEMA + '._versions')} order by aplicada_em, nome")]
    except gexc.NotFound:  # dataset sem as migrações ainda
        return []


def garantir_papeis(engine: Engine) -> None:
    """Só os papéis, sem as migrações — o que a restauração pede antes do `pg_restore` do armazém.

    O dump da memória traz os `GRANT`s de `governance`, `quarantine`, `snapshots` e `raw_legacy` para
    estes papéis, e num armazém recém-criado por `make up` eles ainda não existem: o `pg_restore`
    recusava e desfazia o dump inteiro (RVB5-01). Papel é do *cluster*, não do dump — criá-lo antes
    não conflita com o `--clean` da restauração, e as migrações ficam para o dump trazer."""
    with engine.begin() as conexao:
        _garantir_papeis(conexao)


def garantir(engine: Engine, leitor: tuple[str, str] | None = None) -> list[str]:
    """Aplica as migrações que faltam e devolve os nomes aplicados nesta chamada.

    Com `leitor`, garante também o login de leitura (`_garantir_leitor`)."""
    aplicadas: list[str] = []
    with engine.begin() as conexao:
        conexao.execute(text(f"create schema if not exists {SCHEMA}"))
        conexao.execute(
            text(
                f"create table if not exists {SCHEMA}._versions "
                "(nome text primary key, aplicada_em timestamptz not null default now())"
            )
        )
        feitas = {
            linha[0] for linha in conexao.execute(text(f"select nome from {SCHEMA}._versions"))
        }
        for nome, comandos in MIGRACOES:
            if nome in feitas:
                continue
            for comando in comandos:
                conexao.execute(text(comando))
            conexao.execute(text(f"insert into {SCHEMA}._versions (nome) values (:n)"), {"n": nome})
            aplicadas.append(nome)
        _garantir_papeis(conexao)
        if leitor is not None:
            _garantir_leitor(conexao, *leitor)
    return aplicadas


# ── O log de execução (ADR-0054) ──────────────────────────────────────────────

def _git_do_ambiente(ambiente: dict[str, str] | None = None) -> tuple[str | None, bool | None]:
    """`(commit, sujo)` que o `CARIMBO_ANTES` do `Makefile` exporta; `None` quando não informados."""
    ambiente = os.environ if ambiente is None else ambiente
    commit = ambiente.get("MVP_GIT_COMMIT") or None
    sujo = {"true": True, "false": False}.get((ambiente.get("MVP_GIT_TREE_DIRTY") or "").lower())
    return (commit if commit and re.fullmatch(r"[0-9a-f]{40}", commit) else None), sujo


def abrir(engine: Engine, invocation_id: str, command: str, ambiente: dict[str, str] | None = None) -> None:
    """A primeira fase: a linha `started`, **confirmada** antes de qualquer escrita (o `begin()` sai com `commit`)."""
    commit, sujo = _git_do_ambiente(ambiente)
    with engine.begin() as conexao:
        conexao.execute(text(f"insert into {LOG} (invocation_id, command, git_commit, git_tree_dirty, full_build) "
                             "values (:i, :c, :g, :s, false)"),
                        {"i": invocation_id, "c": command, "g": commit, "s": sujo})


def fechar(engine: Engine, invocation_id: str, status: str, job_id: int | None = None) -> int:
    """A segunda fase de uma escrita fora do dbt: `success` ou `failed`. Só fecha linha aberta."""
    with engine.begin() as conexao:
        return conexao.execute(text(f"update {LOG} set status = :s, finished_at = clock_timestamp(), "
                                    "job_id = coalesce(:j, job_id) where invocation_id = :i and status = 'started'"),
                               {"s": status, "i": invocation_id, "j": job_id}).rowcount


@contextlib.contextmanager
def registrar_mutacao(engine: Engine, command: str, ambiente: dict[str, str] | None = None):
    """Toda escrita suportada do armazém **fora do dbt** passa por aqui (ADR-0054): a linha abre e confirma
    antes, e fecha depois — `success`, ou `failed` se a escrita levantou. Interrompida (o processo morto),
    a linha fica aberta e bloqueia a procedência até `make governance-abandonar`. Devolve o identificador."""
    invocacao = f"{command}-{uuid.uuid4()}"
    abrir(engine, invocacao, command, ambiente)
    try:
        yield invocacao
    except BaseException:
        fechar(engine, invocacao, "failed")
        raise
    fechar(engine, invocacao, "success")


def associar_job(engine: Engine, invocation_id: str, job_id: int) -> None:
    """A sincronização do Airbyte (`airbyte_sync`): o *job* que o POST criou, gravado na linha aberta."""
    with engine.begin() as conexao:
        conexao.execute(text(f"update {LOG} set job_id = :j where invocation_id = :i and status = 'started'"),
                        {"j": job_id, "i": invocation_id})


def fechar_por_job(engine: Engine, job_id: int, estado: str) -> int:
    """O fecho da sincronização quando quem espera **observa** o estado terminal do *job*: `succeeded` é
    `success`; `failed`, `cancelled` e `incomplete` são `failed`. Se quem espera morre, a linha fica aberta."""
    with engine.begin() as conexao:
        return conexao.execute(text(f"update {LOG} set status = :s, finished_at = clock_timestamp() "
                                    "where command = 'airbyte_sync' and job_id = :j and status = 'started'"),
                               {"s": "success" if estado == "succeeded" else "failed", "j": job_id}).rowcount


def abandonar(engine: Engine, invocation_id: str) -> int:
    """O ato explícito do custodiante: a linha aberta passa a `abandoned`, com o instante — nunca a sucesso."""
    with engine.begin() as conexao:
        return conexao.execute(text(f"update {LOG} set status = 'abandoned', abandoned_at = clock_timestamp() "
                                    "where invocation_id = :i and status = 'started'"), {"i": invocation_id}).rowcount


def confirmar_insumos(engine: Engine, invocation_id: str, antes: tuple[str, str, str],
                      depois: tuple[str, str, str]) -> str:
    """`inputs_confirmed` só vira verdadeiro se *commit*, sujeira e digest dos insumos do dbt são, depois do
    dbt, os mesmos de antes (RVL5-3-02). Senão fica falso, e a execução não é verificada.

    Devolve `confirmados`, `mudaram` ou `sem_linha` (o comando não registra: `dbt test`, `docs generate`)."""
    if antes != depois:
        return "mudaram"
    with engine.begin() as conexao:
        n = conexao.execute(text(f"update {LOG} set inputs_confirmed = true where invocation_id = :i"),
                            {"i": invocation_id}).rowcount
    return "confirmados" if n else "sem_linha"


def descartar_snapshots(engine: Engine) -> None:
    """O descarte do histórico SCD (`dbt-build RESET=1`, `dbt-drop-snapshots`), registrado como escrita fora
    do dbt (ADR-0054, RVL5-3-01): a linha abre **antes** de apagar, e uma interrupção a deixa aberta."""
    with registrar_mutacao(engine, "drop_snapshots"):
        with engine.begin() as conexao:
            conexao.execute(text("drop schema if exists snapshots cascade"))


def procedencia(engine: Engine) -> dict:
    """A regra de leitura, que é uma só: a *view* `governance.warehouse_provenance`."""
    with engine.connect() as conexao:
        return dict(conexao.execute(text(f"select * from {PROCEDENCIA}")).mappings().one())


def versoes(engine: Engine) -> list[str]:
    with engine.connect() as conexao:
        try:
            return [
                linha[0]
                for linha in conexao.execute(
                    text(f"select nome from {SCHEMA}._versions order by aplicada_em, nome")
                )
            ]
        except Exception:  # noqa: BLE001 — schema ainda não existe
            return []


def main(argv: list[str] | None = None) -> int:
    """`python -m mvp_ed1.governance garantir` — o que `make dbt-build` chama antes de compilar."""
    import argparse

    from sqlalchemy import create_engine

    from mvp_ed1.db import WAREHOUSE, database_url

    parser = argparse.ArgumentParser(prog="python -m mvp_ed1.governance")
    parser.add_argument("comando", choices=["garantir", "versoes", "procedencia", "abandonar", "confirmar-insumos",
                                                  "descartar-snapshots"])
    parser.add_argument("argumentos", nargs="*")
    args = parser.parse_args(argv)
    engine = create_engine(database_url(WAREHOUSE))
    if args.comando == "descartar-snapshots":
        descartar_snapshots(engine)
        print("  schema snapshots descartado (registrado em governance.dbt_invocations)")
        return 0
    if args.comando == "procedencia":
        estado = procedencia(engine)
        print(" · ".join(f"{k}={v}" for k, v in estado.items()))
        return 0
    if args.comando == "abandonar":
        if len(args.argumentos) != 1:
            parser.error("abandonar INVOCATION_ID")
        n = abandonar(engine, args.argumentos[0])
        print(f"governance: {n} execução aberta marcada abandoned" if n else
              f"governance: nenhuma execução aberta com o id {args.argumentos[0]}")
        return 0 if n else 1
    if args.comando == "confirmar-insumos":
        # INVOCATION COMMIT_ANTES SUJO_ANTES DIGEST_ANTES: o depois é medido aqui.
        if len(args.argumentos) != 4:
            parser.error("confirmar-insumos INVOCATION_ID COMMIT SUJO DIGEST")
        from mvp_ed1.models import pacote

        invocacao, *antes = args.argumentos
        depois = (pacote.commit_atual(), pacote.sujeira_do_build(), pacote.digest_do_dbt())
        resultado = confirmar_insumos(engine, invocacao, tuple(antes), depois)
        print({"confirmados": "governance: insumos do build confirmados no log",
               "mudaram": "governance: aviso — o commit, a sujeira ou os insumos mudaram durante o build; "
                          "a execução não é verificada",
               "sem_linha": "governance: esta execução não escreve o armazém; nada a confirmar"}[resultado])
        return 0
    if args.comando == "garantir":
        leitor = leitor_do_ambiente()
        aplicadas = garantir(engine, leitor)
        print("governance: " + (", ".join(aplicadas) if aplicadas else "nada a aplicar"))
        if leitor is None:
            print(f"governance: aviso — sem {LEITOR_USUARIO} no .env, o login de leitura não foi garantido")
    else:
        print("\n".join(versoes(engine)) or "governance: nenhuma migração aplicada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
