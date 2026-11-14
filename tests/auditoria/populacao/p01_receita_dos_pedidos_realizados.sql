-- P01: a receita líquida da view, por mês, é a dos itens de pedidos realizados em `trusted`.
with camada as (
    select to_char(o.placed_at at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month,
           sum(i.net_revenue_amount) as receita
    from trusted.order_items i
    join trusted.orders o on o.source_system = i.source_system and o.order_id = i.order_id
    where o.is_realised
    group by 1
),
na_view as (
    select year_month, sum(net_revenue_amount) as receita
    from consumption.monthly_revenue_by_channel_and_category group by 1
)
select coalesce(c.year_month, v.year_month), c.receita, v.receita
from camada c full outer join na_view v using (year_month)
where c.receita is distinct from v.receita
