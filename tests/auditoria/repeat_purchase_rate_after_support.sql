-- P16, referência (glossário: recompra pós-pedido; ADR-0036). Pedidos realizados com a janela de
-- 90 dias fechada, no mês do pedido e canal pelo nome; com chamado (por categoria do chamado do
-- pedido) ou sem chamado. Recompra = houve outro pedido realizado em até 90 dias.
with pedidos as (
    select f.source_system, f.order_id, f.date_key, f.sales_channel_key,
           bool_or(f.has_post_order_repeat) as recomprou, max(f.days_to_next_order) as dias
    from analytics.fact_sales_order_item f
    where f.is_realised and f.is_repeat_window_closed
    group by 1, 2, 3, 4
),
categorias as (
    select distinct t.source_system, t.order_id, cat.support_category_name
    from analytics.fact_support_ticket_event t
    join analytics.dim_support_category cat on cat.support_category_key = t.support_category_key
    where t.order_id is not null
),
linhas as (
    select p.*, true as has_support_ticket, c.support_category_name
    from pedidos p join categorias c using (source_system, order_id)
    union all
    select p.*, false, 'Sem chamado'
    from pedidos p
    where not exists (select 1 from categorias c where c.source_system = p.source_system and c.order_id = p.order_id)
)
select d.year_number, d.month_number, d.year_month, ch.sales_channel_name, l.has_support_ticket,
       l.support_category_name, count(*) as order_count,
       count(*) filter (where l.recomprou) as repeat_order_count,
       round(count(*) filter (where l.recomprou)::numeric / nullif(count(*), 0), 4) as repeat_purchase_rate,
       round(avg(l.dias) filter (where l.recomprou), 2) as avg_days_to_next_order
from linhas l
join analytics.dim_date d on d.date_key = l.date_key
join analytics.dim_sales_channel ch on ch.sales_channel_key = l.sales_channel_key
group by 1, 2, 3, 4, 5, 6
