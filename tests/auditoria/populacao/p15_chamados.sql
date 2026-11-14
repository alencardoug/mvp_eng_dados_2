-- P15: os chamados da view, por mês de abertura, são os de `trusted`.
with camada as (
    select to_char(opened_at at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month, count(*) as n
    from trusted.support_tickets group by 1
),
na_view as (
    select year_month, sum(ticket_count) as n from consumption.support_tickets_per_hundred_orders group by 1
)
select coalesce(c.year_month, v.year_month), c.n, v.n
from camada c full outer join na_view v using (year_month)
where c.n is distinct from v.n
