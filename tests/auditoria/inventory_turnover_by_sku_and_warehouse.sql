-- P11, referência (ADR-0052). Para cada SKU × armazém × trimestre com venda: a posição de fim
-- de dia é a soma de todo movimento até o dia; o valor do dia é a posição × (custo das entradas
-- até o dia ÷ quantidade das entradas até o dia); os dias vão do maior entre o início do
-- trimestre e o primeiro movimento do par ao menor entre o fim do trimestre e o último dia do
-- livro da origem. Giro = CMV do trimestre ÷ valor médio, nulo sem valor médio positivo ou com
-- dia de posição sem custo. Construção: junção por intervalo, sem janela acumulada.
with mov as (
    select m.source_system, w.warehouse_natural_key as armazem, p.product_natural_key as produto,
           d.full_date as dia, m.quantity_delta,
           case when m.is_inbound then m.quantity_in else 0 end as qtd_entrada,
           case when m.is_inbound then m.movement_cost_amount else 0 end as custo_entrada
    from analytics.fact_inventory_movement m
    join analytics.dim_date d on d.date_key = m.date_key
    join analytics.dim_product p on p.product_key = m.product_key
    join analytics.dim_warehouse w on w.warehouse_key = m.warehouse_key
),
saidas as (
    select d.year_number, d.quarter_number, p.source_system, p.product_natural_key as produto,
           w.warehouse_natural_key as armazem, p.sku, p.product_name, cat.category_name,
           w.warehouse_name, w.warehouse_region,
           sum(m.quantity_out) as quantity_out, sum(m.cogs_amount) as cost_of_goods_sold
    from analytics.fact_inventory_movement m
    join analytics.dim_date d on d.date_key = m.date_key
    join analytics.dim_product p on p.product_key = m.product_key
    join analytics.dim_warehouse w on w.warehouse_key = m.warehouse_key
    join analytics.dim_category cat on cat.source_system = p.source_system
                                   and cat.category_natural_key = p.product_category_id
    where m.is_sale
    group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
),
pares as (
    select distinct source_system, armazem, produto, year_number, quarter_number from saidas
),
inicio as (select source_system, armazem, produto, min(dia) as primeiro from mov group by 1, 2, 3),
fim as (select source_system, max(dia) as ultimo from mov group by 1),
dias as (
    select pr.*, d.full_date as dia
    from pares pr
    join analytics.dim_date d on d.year_number = pr.year_number and d.quarter_number = pr.quarter_number
    join inicio i using (source_system, armazem, produto)
    join fim f using (source_system)
    where d.full_date between i.primeiro and f.ultimo
),
posicao as (
    select g.source_system, g.armazem, g.produto, g.year_number, g.quarter_number, g.dia,
           sum(m.quantity_delta) as pos, sum(m.qtd_entrada) as qtd, sum(m.custo_entrada) as custo
    from dias g
    join mov m on m.source_system = g.source_system and m.armazem = g.armazem
              and m.produto = g.produto and m.dia <= g.dia
    group by 1, 2, 3, 4, 5, 6
),
media as (
    select source_system, armazem, produto, year_number, quarter_number,
           round(avg(pos::numeric), 2) as avg_qtd,
           case when bool_or(pos <> 0 and qtd = 0) then null
                else round(avg(case when pos = 0 then 0 else pos * custo / nullif(qtd, 0) end), 2) end as avg_valor
    from posicao group by 1, 2, 3, 4, 5
)
select s.year_number, s.quarter_number, s.year_number || '-T' || s.quarter_number as year_quarter,
       s.sku, s.product_name, s.category_name, s.warehouse_name, s.warehouse_region,
       s.quantity_out, s.cost_of_goods_sold,
       coalesce(m.avg_qtd, 0) as avg_quantity_on_hand, m.avg_valor as avg_inventory_value_amount,
       case when m.avg_valor > 0 then round(s.cost_of_goods_sold / m.avg_valor, 2) end as inventory_turnover
from saidas s
left join media m using (source_system, armazem, produto, year_number, quarter_number)
