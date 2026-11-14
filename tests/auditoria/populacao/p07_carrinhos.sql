-- P07: os carrinhos da view, por mês de criação, são os carrinhos **com item** de `trusted`
-- (glossário: taxa de conversão). Em 14/11/2026, 145 carrinhos sem item ficam de fora por
-- definição, 14 deles marcados como convertidos (observação da auditoria).
with camada as (
    select to_char(cart_created_at at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month, count(*) as n
    from trusted.carts where item_count > 0 group by 1
),
na_view as (
    select year_month, sum(cart_count) as n from consumption.cart_conversion_rate_by_channel group by 1
)
select coalesce(c.year_month, v.year_month), c.n, v.n
from camada c full outer join na_view v using (year_month)
where c.n is distinct from v.n
