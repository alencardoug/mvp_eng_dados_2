-- P01, referência (Bloco 1b). Do glossário: receita líquida e bruta, desconto e
-- quantidade dos itens de pedidos realizados, por mês, canal e categoria pelo nome.
-- Construção: primeiro o pedido em cada recorte, depois a soma dos pedidos.
with por_pedido as (
    select d.year_month, d.year_number, d.month_number,
           ch.sales_channel_name, ch.channel_type, cat.root_category_name, cat.category_name,
           f.source_system, f.order_id,
           sum(f.quantity) as unidades, sum(f.gross_revenue_amount) as bruta,
           sum(f.discount_amount) as desconto, sum(f.net_revenue_amount) as liquida
    from analytics.fact_sales_order_item f
    join analytics.dim_date d on d.date_key = f.date_key
    join analytics.dim_sales_channel ch on ch.sales_channel_key = f.sales_channel_key
    join analytics.dim_category cat on cat.category_key = f.category_key
    where f.is_realised
    group by 1, 2, 3, 4, 5, 6, 7, 8, 9
)
select year_month, year_number, month_number, sales_channel_name, channel_type,
       root_category_name, category_name,
       count(*) as order_count, sum(unidades) as unit_count, sum(bruta) as gross_revenue_amount,
       sum(desconto) as discount_amount, sum(liquida) as net_revenue_amount
from por_pedido
group by 1, 2, 3, 4, 5, 6, 7
