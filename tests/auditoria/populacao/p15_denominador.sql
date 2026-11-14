-- P15: o denominador de cada mês e canal pelo nome é o número de pedidos realizados de `trusted`
-- naquele mês e canal, todas as origens (antes da revisão da auditoria, 15 pedidos do legado de
-- itens rejeitados em cascata ficavam de fora, F21).
with camada as (
    select to_char(o.placed_at at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month,
           ch.sales_channel_name, count(*)::numeric as n
    from trusted.orders o
    join analytics.dim_sales_channel ch
      on ch.source_system = o.source_system and ch.sales_channel_natural_key = o.sales_channel_id
    where o.is_realised
    group by 1, 2
),
na_view as (
    -- Os nulos ficam: um denominador nulo num canal que tem pedidos em `trusted` é perda, e só o
    -- "Sem canal", sem pedido nenhum, pode ser nulo (RVB1b-2-01).
    select distinct year_month, sales_channel_name, channel_order_count as n
    from consumption.support_tickets_per_hundred_orders
)
select v.year_month, v.sales_channel_name, c.n, v.n
from na_view v left join camada c using (year_month, sales_channel_name)
where c.n is distinct from v.n
