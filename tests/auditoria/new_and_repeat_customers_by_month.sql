-- P04, referência. Do glossário (recorrência de compra): o cliente estreia no mês do seu
-- primeiro pedido realizado, no canal e no segmento daquele pedido, e é recorrente se fez
-- outro pedido realizado em até 90 dias corridos da estreia. A coorte é a da estreia. Todo
-- pedido conta, inclusive o de itens rejeitados em cascata (Q7): lê o grão do pedido.
with pedidos as (
    select c.source_system, c.customer_natural_key, f.order_id, f.placed_at, f.date_key,
           f.sales_channel_key, c.customer_segment_name
    from analytics.fact_order_status_event f
    join analytics.dim_customer c on c.customer_key = f.customer_key
    where f.is_order_creation and f.is_realised
),
ordem as (
    select p.*, row_number() over (partition by source_system, customer_natural_key
                                    order by placed_at, order_id) as n
    from pedidos p
),
estreia as (select * from ordem where n = 1),
volta as (
    select e.source_system, e.customer_natural_key,
           bool_or(o.placed_at > e.placed_at and o.placed_at <= e.placed_at + interval '90 days') as voltou
    from estreia e join pedidos o using (source_system, customer_natural_key)
    group by 1, 2
)
select d.year_month, d.year_number, d.month_number, ch.sales_channel_name, e.customer_segment_name,
       count(*) as new_customer_count,
       count(*) filter (where v.voltou) as returning_customer_count,
       round(100.0 * count(*) filter (where v.voltou) / nullif(count(*), 0), 2) as repeat_purchase_rate_pct
from estreia e
join volta v using (source_system, customer_natural_key)
join analytics.dim_date d on d.date_key = e.date_key
join analytics.dim_sales_channel ch on ch.sales_channel_key = e.sales_channel_key
group by 1, 2, 3, 4, 5
