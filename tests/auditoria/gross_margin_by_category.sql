-- P08, referência. Lucro bruto = receita líquida (pedidos realizados, mês do pedido) − CMV
-- (saídas de venda do livro, mês da expedição, categoria do produto), por mês e categoria pelo
-- nome, combinados por drill across; margem = lucro ÷ receita.
with receita as (
    select d.year_month, d.year_number, d.month_number, cat.root_category_name, cat.category_name,
           sum(f.net_revenue_amount) as receita, sum(f.quantity) as unidades
    from analytics.fact_sales_order_item f
    join analytics.dim_date d on d.date_key = f.date_key
    join analytics.dim_category cat on cat.category_key = f.category_key
    where f.is_realised
    group by 1, 2, 3, 4, 5
),
custo as (
    select d.year_month, d.year_number, d.month_number, cat.root_category_name, cat.category_name,
           sum(m.cogs_amount) as custo, sum(m.quantity_out) as expedidas
    from analytics.fact_inventory_movement m
    join analytics.dim_date d on d.date_key = m.date_key
    join analytics.dim_product p on p.product_key = m.product_key
    join analytics.dim_category cat on cat.source_system = p.source_system
                                   and cat.category_natural_key = p.product_category_id
    where m.is_sale
    group by 1, 2, 3, 4, 5
),
chaves as (
    select year_month, year_number, month_number, root_category_name, category_name from receita
    union
    select year_month, year_number, month_number, root_category_name, category_name from custo
)
select k.year_month, k.year_number, k.month_number, k.root_category_name, k.category_name,
       coalesce(r.receita, 0) as net_revenue_amount, coalesce(c.custo, 0) as cost_of_goods_sold,
       coalesce(r.receita, 0) - coalesce(c.custo, 0) as gross_profit_amount,
       round(100.0 * (coalesce(r.receita, 0) - coalesce(c.custo, 0)) / nullif(r.receita, 0), 2) as gross_margin_pct,
       coalesce(r.unidades, 0) as unit_count, coalesce(c.expedidas, 0) as dispatched_unit_count
from chaves k
left join receita r using (year_month, root_category_name, category_name)
left join custo c using (year_month, root_category_name, category_name)
