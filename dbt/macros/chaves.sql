{#-
    As chaves de `analytics` (ADR-0056, F10): a PK nasce com a tabela, pelo contrato; as FKs vivem entre
    execuções, nunca durante uma.

    **Por que as FKs saem e voltam.** O dbt recria cada tabela por troca de nomes e apaga a antiga com
    `drop … cascade`: a FK de uma fato para a dimensão recriada cai junto, e a fato incremental, que não se
    recria, não a recupera — perde a FK na segunda execução normal e passa a receber órfão calada. Instalar
    só no fim não basta: com quatro *threads*, duas tabelas ligadas por FK se reconstroem ao mesmo tempo, e
    o `cascade` de uma trava na FK da outra (`deadlock detected`, medido no Bloco 6). Então:

    * `retirar_chaves_estrangeiras()` — no `on-run-start`, depois da abertura do log: toda FK de `analytics`
      sai, e nenhum `cascade` cruza modelos durante a execução;
    * `instalar_chaves()` — no `on-run-end`, depois do acesso e antes do fecho: a PK declarada que falta
      (a incremental que já existia sem ela) e cada FK, conferidas pela definição inteira.

    **Quem as declara.** A PK é a `constraints: [{type: primary_key}]` da coluna, no `.yml`. A FK é a
    `relationships` de `analytics` para `analytics`: nada se declara duas vezes. A guarda
    `tests/test_chaves.py` recusa a `relationships` que fuja dessa forma.

    **Quando agem** (`_age_nas_chaves`): só em `run` e `build` cuja seleção tem modelo de `analytics`, ou
    que chegam à execução com a seleção vazia — o `dbt retry`, que monta a fila sem o seletor e pode
    reconstruir `analytics` sem dizer o quê (medido); e só com a abertura **desta** invocação confirmada no
    log, porque a falha da abertura não impede o `on-run-end` (medido) e nenhuma *constraint* muda sem
    registro (ADR-0054). O mesmo predicado grava o escopo `analytics` na abertura, que admite uma invocação
    dessas de cada vez (`log_de_execucao.sql`, Q38).

    **A falha.** Com órfão, a instalação falha, a execução sai com erro, o fecho não grava e a procedência
    fica `not_verified`; as linhas ficam, e a recuperação é a de Execução Local. Nenhuma linha se apaga para
    a FK passar.

    **No BigQuery** as duas são `NOT ENFORCED`, pelo mesmo predicado; o despacho de lá não foi exercitado
    nesta fase (L9).
-#}

{% macro _schema_analytics() -%}
    {%- for no in graph.nodes.values() if no.resource_type == 'model' and no.config.schema == 'analytics' -%}
        {{- return(no.schema) -}}
    {%- endfor -%}
    {{- return('analytics') -}}
{%- endmacro %}


{% macro _age_nas_chaves() -%}
    {%- if not execute or flags.WHICH not in ['run', 'build'] -%}{{ return(false) }}{%- endif -%}
    {%- if selected_resources | length == 0 -%}{{ return(true) }}{%- endif -%}
    {%- set esquema = _schema_analytics() -%}
    {%- for uid in selected_resources -%}
        {%- set no = graph.nodes.get(uid) -%}
        {%- if no is not none and no.resource_type == 'model' and no.schema == esquema -%}{{ return(true) }}{%- endif -%}
    {%- endfor -%}
    {{ return(false) }}
{%- endmacro %}


{% macro _abertura_confirmada() -%}
    {%- set linha = run_query("select 1 from governance.dbt_invocations where invocation_id = '" ~ invocation_id ~ "' and status = 'started'") -%}
    {{ return(linha.rows | length == 1) }}
{%- endmacro %}


{#- As PKs declaradas e as FKs das `relationships`, como o grafo as diz: só de `analytics` para `analytics`. -#}
{% macro _chaves_declaradas() -%}
    {%- set esquema = _schema_analytics() -%}
    {%- set modelos = {} -%}
    {%- for no in graph.nodes.values() if no.resource_type == 'model' and no.schema == esquema -%}
        {%- do modelos.update({no.name: no}) -%}
    {%- endfor -%}
    {%- set pks = [] -%}
    {%- for no in modelos.values() -%}
        {%- for c in no.columns.values() if (c.constraints | selectattr('type', 'equalto', 'primary_key') | list) -%}
            {%- do pks.append({'tabela': no.alias or no.name, 'coluna': c.name}) -%}
        {%- endfor -%}
    {%- endfor -%}
    {%- set fks = [] -%}
    {%- for t in graph.nodes.values() if t.resource_type == 'test' and (t.test_metadata or {}).get('name') == 'relationships' -%}
        {%- set filho = graph.nodes.get(t.attached_node) -%}
        {%- set alvo = (t.test_metadata.kwargs.to or '').split("'") -%}
        {%- set pai = modelos.get(alvo[1]) if alvo | length == 3 else none -%}
        {%- if filho is not none and filho.name in modelos and pai is not none -%}
            {%- do fks.append({'tabela': filho.alias or filho.name, 'coluna': t.column_name,
                               'pai': pai.alias or pai.name, 'coluna_pai': t.test_metadata.kwargs.field,
                               'nome': 'fk_' ~ (filho.alias or filho.name) ~ '__' ~ t.column_name}) -%}
        {%- endif -%}
    {%- endfor -%}
    {{ return({'esquema': esquema, 'pks': pks, 'fks': fks}) }}
{%- endmacro %}


{% macro retirar_chaves_estrangeiras() -%}
    {%- if _age_nas_chaves() and _abertura_confirmada() -%}
        {%- do adapter.dispatch('retirar_chaves_estrangeiras')(_schema_analytics()) -%}
    {%- endif -%}
    select 1
{%- endmacro %}

{% macro default__retirar_chaves_estrangeiras(esquema) -%}
    {%- set fks = run_query("select conrelid::regclass::text, quote_ident(conname) from pg_constraint
        where contype = 'f' and connamespace = to_regnamespace('" ~ esquema ~ "')") -%}
    {%- for r in fks.rows -%}
        {%- do run_query("alter table " ~ r[0] ~ " drop constraint " ~ r[1]) -%}
    {%- endfor -%}
    {%- do log("chaves: " ~ (fks.rows | length) ~ " FKs de " ~ esquema ~ " retiradas", info=true) -%}
{%- endmacro %}

{% macro bigquery__retirar_chaves_estrangeiras(esquema) -%}
    {#- Não exercitado nesta fase (L9). -#}
    {%- set base = target.project ~ '.' ~ esquema -%}
    {%- set fks = run_query("select table_name, constraint_name from `" ~ base ~ "`.INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        where constraint_type = 'FOREIGN KEY'") -%}
    {%- for r in fks.rows -%}
        {%- do run_query("alter table `" ~ base ~ "." ~ r[0] ~ "` drop constraint `" ~ r[1] ~ "`") -%}
    {%- endfor -%}
{%- endmacro %}


{% macro instalar_chaves() -%}
    {%- if _age_nas_chaves() and _abertura_confirmada() -%}
        {%- do adapter.dispatch('instalar_chaves')(_chaves_declaradas()) -%}
    {%- endif -%}
    select 1
{%- endmacro %}

{% macro default__instalar_chaves(chaves) -%}
    {%- set esquema = chaves.esquema -%}
    {%- set instaladas = [] -%}
    {%- for pk in chaves.pks -%}
        {%- set rel = esquema ~ '.' ~ pk.tabela -%}
        {%- if run_query("select to_regclass('" ~ rel ~ "') is not null").rows[0][0] -%}
            {%- set tem = run_query("select count(*) from pg_constraint where conrelid = '" ~ rel ~ "'::regclass and contype = 'p'").rows[0][0] -%}
            {%- if tem == 0 -%}
                {%- do run_query("alter table " ~ rel ~ " add primary key (" ~ pk.coluna ~ ")") -%}
                {%- do instaladas.append('PK ' ~ pk.tabela) -%}
            {%- endif -%}
        {%- endif -%}
    {%- endfor -%}
    {%- for fk in chaves.fks -%}
        {%- set filho = esquema ~ '.' ~ fk.tabela -%}
        {%- set pai = esquema ~ '.' ~ fk.pai -%}
        {%- if run_query("select to_regclass('" ~ filho ~ "') is not null and to_regclass('" ~ pai ~ "') is not null").rows[0][0] -%}
            {#- Pela definição inteira: a tabela, a apontada e as colunas dos dois lados. -#}
            {%- set tem = run_query("select count(*) from pg_constraint k
                where k.contype = 'f' and k.conrelid = '" ~ filho ~ "'::regclass and k.confrelid = '" ~ pai ~ "'::regclass
                  and k.conkey = array[(select attnum from pg_attribute where attrelid = k.conrelid and attname = '" ~ fk.coluna ~ "')]
                  and k.confkey = array[(select attnum from pg_attribute where attrelid = k.confrelid and attname = '" ~ fk.coluna_pai ~ "')]").rows[0][0] -%}
            {%- if tem == 0 -%}
                {%- do run_query("alter table " ~ filho ~ " add constraint " ~ fk.nome ~ " foreign key (" ~ fk.coluna
                                 ~ ") references " ~ pai ~ " (" ~ fk.coluna_pai ~ ")") -%}
                {%- do instaladas.append(fk.nome) -%}
            {%- endif -%}
        {%- endif -%}
    {%- endfor -%}
    {%- do log("chaves: " ~ (instaladas | length) ~ " instaladas em " ~ esquema ~ " (" ~ (chaves.pks | length)
               ~ " PKs e " ~ (chaves.fks | length) ~ " FKs declaradas)", info=true) -%}
{%- endmacro %}

{% macro bigquery__instalar_chaves(chaves) -%}
    {#- Não exercitado nesta fase (L9). A PK já sai pelo contrato, `NOT ENFORCED`; aqui só as FKs que faltam. -#}
    {%- set base = target.project ~ '.' ~ chaves.esquema -%}
    {%- set existentes = run_query("select constraint_name from `" ~ base ~ "`.INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        where constraint_type = 'FOREIGN KEY'").columns[0].values() -%}
    {%- for fk in chaves.fks if fk.nome not in existentes -%}
        {%- do run_query("alter table `" ~ base ~ "." ~ fk.tabela ~ "` add constraint `" ~ fk.nome ~ "` foreign key ("
                         ~ fk.coluna ~ ") references `" ~ base ~ "." ~ fk.pai ~ "` (" ~ fk.coluna_pai ~ ") not enforced") -%}
    {%- endfor -%}
{%- endmacro %}
