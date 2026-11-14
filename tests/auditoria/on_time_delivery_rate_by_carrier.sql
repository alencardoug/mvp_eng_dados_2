-- P13, referência (ADR-0033, ADR-0053). Toda remessa entregue, no mês da chegada, por
-- transportadora, modalidade e armazém; no prazo = chegou até a promessa.
select d.year_number, d.month_number, d.year_month, c.carrier_name, c.service_level,
       w.warehouse_name, w.warehouse_region,
       count(*) as delivered_count,
       count(*) filter (where s.is_on_time) as on_time_count,
       count(*) filter (where not s.is_on_time) as late_count,
       count(*) filter (where s.is_split_order) as split_order_shipment_count,
       round(count(*) filter (where s.is_on_time)::numeric / nullif(count(*), 0), 4) as on_time_rate,
       round(avg(s.delivery_delay_days) filter (where not s.is_on_time), 4) as avg_delay_days_when_late,
       round(avg(s.transit_days), 4) as avg_transit_days,
       sum(s.failed_attempt_count)::numeric as failed_attempt_count
from analytics.fact_shipment s
join analytics.dim_date d on d.date_key = s.delivered_date_key
join analytics.dim_carrier c on c.carrier_key = s.carrier_key
join analytics.dim_warehouse w on w.warehouse_key = s.warehouse_key
where s.is_delivered
group by 1, 2, 3, 4, 5, 6, 7
