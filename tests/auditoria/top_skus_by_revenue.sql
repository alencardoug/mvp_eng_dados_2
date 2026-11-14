-- P03, referência. Os 25 SKUs (por origem e chave natural) de maior receita líquida de
-- pedidos realizados, com empates no mesmo posto, e o peso de cada um na receita da categoria
-- pelo nome, somando as origens.
with por_sku as (
    select p.source_system, p.product_natural_key, p.sku, p.product_name,
           cat.category_name, cat.root_category_name, b.brand_name,
           bool_or(p.is_deleted) as is_deleted,
           sum(f.quantity) as unit_count, sum(f.net_revenue_amount) as net_revenue_amount
    from analytics.fact_sales_order_item f
    join analytics.dim_product p on p.product_key = f.product_key
    join analytics.dim_category cat on cat.category_key = f.category_key
    left join analytics.dim_brand b on b.brand_key = f.brand_key
    where f.is_realised
    group by 1, 2, 3, 4, 5, 6, 7
),
categoria as (
    select category_name, sum(net_revenue_amount) as total from por_sku group by 1
),
postos as (
    select s.*, (select count(*) from por_sku o where o.net_revenue_amount > s.net_revenue_amount) + 1 as revenue_rank
    from por_sku s
)
select p.revenue_rank, p.product_natural_key, p.sku, p.product_name, p.category_name,
       p.root_category_name, p.brand_name, p.is_deleted, p.unit_count, p.net_revenue_amount,
       c.total as category_net_revenue_amount,
       round(100 * p.net_revenue_amount / nullif(c.total, 0), 2) as category_revenue_share_pct
from postos p join categoria c using (category_name)
where p.revenue_rank <= 25
