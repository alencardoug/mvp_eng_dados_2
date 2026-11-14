-- P02: os pedidos da view, por mês, são os pedidos realizados de `trusted` **com item aceito**.
-- Recorte declarado (F21): o pedido cujos itens foram todos para a quarentena fica fora do ticket
-- médio, porque a receita dele não é conhecida; contá-lo com receita zero baixaria o ticket. Em
-- 14/11/2026, 15 pedidos do legado. Vale para o order_count das outras views de receita (P01, P05,
-- P06), que contam pedidos ao lado da receita do mesmo item.
with camada as (
    select to_char(o.placed_at at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month, count(*) as n
    from trusted.orders o
    where o.is_realised
      and exists (select 1 from trusted.order_items i where i.source_system = o.source_system and i.order_id = o.order_id)
    group by 1
),
na_view as (
    -- Cada pedido cai numa célula só (um canal, uma versão do cliente): a soma do mês é o total.
    select year_month, sum(order_count) as n
    from consumption.average_order_value_by_channel_and_segment
    group by 1
)
select coalesce(c.year_month, v.year_month), c.n, v.n
from camada c full outer join na_view v using (year_month)
where c.n is distinct from v.n
