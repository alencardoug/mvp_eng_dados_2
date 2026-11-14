-- P05, referência. Receita líquida, pedidos e unidades de pedidos realizados por trimestre,
-- lugar de entrega e canal pelo nome; as versões de cliente distintas ao lado.
select d.year_number, d.quarter_number, d.year_number || '-T' || d.quarter_number as year_quarter,
       g.region, g.state_code, g.state_name, ch.sales_channel_name,
       count(distinct f.source_system || ':' || f.order_id) as order_count,
       count(distinct f.customer_key) as customer_version_count,
       sum(f.quantity) as unit_count, sum(f.net_revenue_amount) as net_revenue_amount
from analytics.fact_sales_order_item f
join analytics.dim_date d on d.date_key = f.date_key
join analytics.dim_geography g on g.geography_key = f.geography_key
join analytics.dim_sales_channel ch on ch.sales_channel_key = f.sales_channel_key
where f.is_realised
group by 1, 2, 3, 4, 5, 6, 7
