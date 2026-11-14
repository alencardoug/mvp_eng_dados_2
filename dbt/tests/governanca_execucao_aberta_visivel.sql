-- A abertura do log desta invocação está confirmada e visível de outra conexão, durante a
-- execução (ADR-0054, RVL5-2-02): o teste roda numa conexão de nó, e não na do `on-run-start`.
-- Só nos comandos que registram; nos outros (o `dbt test` sozinho) não há linha a ver.
{% if flags.WHICH in ['build', 'run', 'seed', 'snapshot'] %}
select '{{ invocation_id }}' as invocation_id
where not exists (
    select 1 from governance.dbt_invocations
    where invocation_id = '{{ invocation_id }}' and status = 'started'
)
{% else %}
select null as invocation_id where false
{% endif %}
