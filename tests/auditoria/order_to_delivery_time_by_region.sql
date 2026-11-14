-- P14, referência (glossário: ciclo de entrega). Um pedido por linha, só com o ciclo fechado
-- (todas as remessas entregues), no mês da chegada da última remessa, pela região do cliente e
-- pela modalidade e transportadora da remessa que fechou o ciclo. Todo pedido, inclusive o de
-- itens rejeitados em cascata: lê a fato de remessa (ADR-0053).
with pedidos as (
    select f.source_system, f.order_id, f.delivered_date_key, f.geography_key, f.carrier_key,
           f.is_split_order, f.order_shipment_count, f.order_to_delivery_days
    from analytics.fact_shipment f
    where f.is_cycle_closing_shipment and f.is_order_cycle_closed
)
select d.year_number, d.month_number, d.year_month, g.region, g.state_code, c.service_level, c.carrier_name,
       count(*) as order_count, count(*) filter (where p.is_split_order) as split_order_count,
       sum(p.order_shipment_count)::numeric as shipment_count,
       round(avg(p.order_to_delivery_days), 4) as avg_order_to_delivery_days,
       round((percentile_cont(0.5) within group (order by p.order_to_delivery_days))::numeric, 4) as median_order_to_delivery_days,
       round(max(p.order_to_delivery_days), 4) as max_order_to_delivery_days
from pedidos p
join analytics.dim_date d on d.date_key = p.delivered_date_key
join analytics.dim_geography g on g.geography_key = p.geography_key
join analytics.dim_carrier c on c.carrier_key = p.carrier_key
group by 1, 2, 3, 4, 5, 6, 7
