-- P02, referência. Ticket médio = receita líquida ÷ pedidos realizados distintos, por mês,
-- canal pelo nome e segmento do cliente na versão vigente no pedido.
with por_pedido as (
    select d.year_month, d.year_number, d.month_number, ch.sales_channel_name, c.customer_segment_name,
           f.source_system, f.order_id, sum(f.net_revenue_amount) as liquida
    from analytics.fact_sales_order_item f
    join analytics.dim_date d on d.date_key = f.date_key
    join analytics.dim_sales_channel ch on ch.sales_channel_key = f.sales_channel_key
    join analytics.dim_customer c on c.customer_key = f.customer_key
    where f.is_realised
    group by 1, 2, 3, 4, 5, 6, 7
)
select year_month, year_number, month_number, sales_channel_name, customer_segment_name,
       count(*) as order_count, sum(liquida) as net_revenue_amount,
       round(sum(liquida) / nullif(count(*), 0), 2) as average_order_value
from por_pedido
group by 1, 2, 3, 4, 5
