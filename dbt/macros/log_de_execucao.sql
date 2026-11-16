{#-
    O log de execução do dbt em `governance.dbt_invocations` (ADR-0054), em duas fases.

    * `registrar_abertura()` — no `on-run-start`: a linha `started` desta invocação, **confirmada**
      (`commit` explícito: o perfil PostgreSQL não tem *autocommit*, e devolver o `insert` ao dbt não o
      persistiria, RVL5-2-02). Se ela falha, o dbt pula os nós (`skip_nodes_if_on_run_start_fails`).
    * `registrar_fecho(results)` — no `on-run-end`, **por último**, depois do acesso: o fecho, com as
      contagens por estado, o `status` e o `full_build`. Se um *hook* anterior falha, o dbt pula este, e a
      linha fica aberta — o que bloqueia a procedência, de propósito.

    Só os comandos que escrevem o armazém registram: `build`, `run`, `seed`, `snapshot` (e o `retry` deles,
    que herda o comando). `full_build` é **medido**: os resultados executados cobrem todo nó do grafo
    (modelos, *seeds*, *snapshots*, testes) **e** todo teste de unidade e toda função habilitados, que o
    dbt guarda em coleções à parte, `graph.unit_tests` e `graph.functions` (RVL5I-1-01, RVL5I-2-01). O `retry`, o `--select` e o
    `--exclude-resource-type unit_test` não cobrem (RVL5-2-01). O commit e a
    sujeira vêm do ambiente que o `CARIMBO_ANTES` do `Makefile` exporta; sem ele (a DAG), ficam nulos.
-#}

{% macro _escreve_o_armazem() -%}
    {{ return(execute and flags.WHICH in ['build', 'run', 'seed', 'snapshot']) }}
{%- endmacro %}


{% macro registrar_abertura() -%}
    {%- if _escreve_o_armazem() -%}
        {%- set commit = env_var('MVP_GIT_COMMIT', '') -%}
        {%- set sujo = env_var('MVP_GIT_TREE_DIRTY', '') | lower -%}
        {#- O escopo `analytics` admite uma invocação dessas de cada vez (ADR-0056): a segunda, com a primeira
            aberta, viola o índice parcial do log, a abertura falha e os nós são pulados. -#}
        insert into governance.dbt_invocations (invocation_id, command, git_commit, git_tree_dirty, dbt_version, target, exclusive_scope)
        values (
            '{{ invocation_id }}',
            '{{ flags.WHICH }}',
            {{ "'" ~ commit ~ "'" if modules.re.fullmatch('[0-9a-f]{40}', commit) else 'null' }},
            {{ sujo if sujo in ['true', 'false'] else 'null' }},
            '{{ dbt_version }}',
            '{{ target.name }}',
            {{ "'analytics'" if _age_nas_chaves() else 'null' }}
        );
        commit;
    {%- else -%}
        select 1
    {%- endif -%}
{%- endmacro %}


{% macro registrar_fecho(results) -%}
    {%- if _escreve_o_armazem() -%}
        {%- set contagem = {} -%}
        {%- set executados = [] -%}
        {%- for r in results -%}
            {%- set estado = r.status | string -%}
            {%- do contagem.update({estado: contagem.get(estado, 0) + 1}) -%}
            {#- `reused` e `no-op` não executaram: não contam para a cobertura -#}
            {%- if estado not in ['reused', 'no-op'] and r.node is not none -%}
                {%- do executados.append(r.node.unique_id) -%}
            {%- endif -%}
        {%- endfor -%}
        {%- set faltam = [] -%}
        {%- for no in graph.nodes.values() if no.resource_type in ['model', 'seed', 'snapshot', 'test'] -%}
            {%- if no.unique_id not in executados -%}{%- do faltam.append(no.unique_id) -%}{%- endif -%}
        {%- endfor -%}
        {#- os testes de unidade e as funções não estão em `graph.nodes` (RVL5I-1-01, RVL5I-2-01) -#}
        {%- for colecao in ['unit_tests', 'functions'] -%}
            {%- for outro in graph.get(colecao, {}).values() -%}
                {%- if outro.unique_id not in executados -%}{%- do faltam.append(outro.unique_id) -%}{%- endif -%}
            {%- endfor -%}
        {%- endfor -%}
        {%- set integral = flags.WHICH == 'build' and faltam | length == 0 and not flags.EMPTY -%}
        {%- set reprovou = contagem.keys() | select('in', ['error', 'fail', 'runtime error', 'skipped', 'partial success']) | list -%}
        update governance.dbt_invocations
        set status = '{{ "failed" if reprovou else "success" }}',
            finished_at = clock_timestamp(),
            full_build = {{ 'true' if integral else 'false' }},
            result_counts = '{{ tojson(contagem) }}'::jsonb
        where invocation_id = '{{ invocation_id }}' and status = 'started';
        commit;
    {%- else -%}
        select 1
    {%- endif -%}
{%- endmacro %}


{#- Só para o teste de integração que prova a linha aberta quando um *hook* do fim falha antes do fecho. -#}
{% macro falha_de_teste_antes_do_fecho() -%}
    {%- if var('mvp_teste_falhar_antes_do_fecho', false) -%}
        {{ exceptions.raise_compiler_error('falha de teste antes do fecho do log (mvp_teste_falhar_antes_do_fecho)') }}
    {%- endif -%}
    select 1
{%- endmacro %}
