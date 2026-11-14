-- P07, referência. Conversão = convertidos ÷ fechados, pela data de criação do carrinho,
-- por mês e canal pelo nome; valores ao lado.
select d.year_month, d.year_number, d.month_number, ch.sales_channel_name, ch.channel_type,
       sum(f.cart_count) as cart_count, sum(f.closed_cart_count) as closed_cart_count,
       sum(f.converted_cart_count) as converted_cart_count, sum(f.abandoned_cart_count) as abandoned_cart_count,
       round(100.0 * sum(f.converted_cart_count) / nullif(sum(f.closed_cart_count), 0), 2) as cart_conversion_rate_pct,
       sum(f.cart_value_amount) as cart_value_amount, sum(f.abandoned_value_amount) as abandoned_value_amount
from analytics.fact_cart_event f
join analytics.dim_date d on d.date_key = f.cart_created_date_key
join analytics.dim_sales_channel ch on ch.sales_channel_key = f.sales_channel_key
group by 1, 2, 3, 4, 5
