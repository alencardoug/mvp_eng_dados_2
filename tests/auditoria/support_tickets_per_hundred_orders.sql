-- P15, referência (Perguntas de Negócio, "Como se conta"). Chamados abertos por mês, canal e
-- categoria pelo nome; pedidos realizados distintos por mês e canal pelo nome, somando as origens.
with chamados as (
    select d.year_number, d.month_number, d.year_month, ch.sales_channel_name, ch.channel_type,
           cat.support_category_name, cat.support_category_group,
           count(*) as ticket_count,
           count(*) filter (where t.ticket_priority in ('high', 'urgent')) as high_priority_ticket_count,
           count(*) filter (where t.was_reopened) as reopened_ticket_count,
           count(*) filter (where t.is_solved_first_time) as solved_first_time_count,
           round(avg(t.hours_to_resolution), 2) as avg_hours_to_resolution
    from analytics.fact_support_ticket_event t
    join analytics.dim_date d on d.date_key = t.date_key
    join analytics.dim_sales_channel ch on ch.sales_channel_key = t.sales_channel_key
    join analytics.dim_support_category cat on cat.support_category_key = t.support_category_key
    where t.is_ticket_creation
    group by 1, 2, 3, 4, 5, 6, 7
),
pedidos as (
    select d.year_month, ch.sales_channel_name,
           count(distinct f.source_system || ':' || f.order_id)::numeric as channel_order_count
    from analytics.fact_sales_order_item f
    join analytics.dim_date d on d.date_key = f.date_key
    join analytics.dim_sales_channel ch on ch.sales_channel_key = f.sales_channel_key
    where f.is_realised
    group by 1, 2
)
select c.year_number, c.month_number, c.year_month, c.sales_channel_name, c.channel_type,
       c.support_category_name, c.support_category_group, c.ticket_count, c.high_priority_ticket_count,
       c.reopened_ticket_count, c.solved_first_time_count, p.channel_order_count,
       round(c.ticket_count * 100.0 / nullif(p.channel_order_count, 0), 4) as tickets_per_hundred_orders,
       c.avg_hours_to_resolution
from chamados c
left join pedidos p using (year_month, sales_channel_name)
