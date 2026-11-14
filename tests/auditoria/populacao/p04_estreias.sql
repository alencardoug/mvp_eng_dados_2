-- P04: as estreias da view, por mês, são as dos clientes de `trusted` pelo primeiro pedido
-- realizado, inclusive o de itens rejeitados em cascata (Q7; antes da correção da auditoria,
-- 1 cliente sem estreia e 6 com a estreia num mês mais tarde).
with primeiros as (
    select o.source_system, o.customer_id, min(o.placed_at) as estreia
    from trusted.orders o
    where o.is_realised
    group by 1, 2
),
camada as (
    select to_char(estreia at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month, count(*) as n
    from primeiros group by 1
),
na_view as (
    select year_month, sum(new_customer_count) as n from consumption.new_and_repeat_customers_by_month group by 1
)
select coalesce(c.year_month, v.year_month), c.n, v.n
from camada c full outer join na_view v using (year_month)
where c.n is distinct from v.n
