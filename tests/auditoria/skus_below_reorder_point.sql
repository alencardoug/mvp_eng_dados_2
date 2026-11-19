-- P12, referência (glossário: ruptura e cobertura de estoque; Streaming §4.1). A posição é a do
-- livro inteiro: os movimentos da fato mais os deltas do caminho quente que a fato ainda não
-- absorveu (a fronteira é a ausência do movement_id na fato, não um corte por tempo). O
-- disponível é a posição menos o reservado da projeção. Entra o par cujo disponível está abaixo
-- do ponto de reposição do par (ADR-0057), calculado aqui sem ler `dim_sku_location`: só o lado frio
-- (a fato), a venda dos `:janela_do_ponto` dias até o último movimento da fato, teto da razão vezes
-- `:prazo_de_reposicao` + `:margem_de_seguranca`; zero sem venda ou sem linha na fato. Demanda = unidades vendidas na janela de cobertura (`cover_window_days`) até o último instante do
-- livro, por dia; cobertura = disponível ÷ demanda, indefinida sem venda.
with livro as (
    select f.source_system, w.warehouse_natural_key as armazem, p.product_natural_key as produto,
           f.quantity_delta, f.quantity_out, f.is_sale, f.occurred_at, false as quente
    from analytics.fact_inventory_movement f
    join analytics.dim_warehouse w on w.warehouse_key = f.warehouse_key
    join analytics.dim_product p on p.product_key = f.product_key
    union all
    select 'retail', s.warehouse_id, s.product_variant_id, s.quantity_delta::integer,
           greatest(-s.quantity_delta, 0)::integer, s.movement_type = 'sale_dispatch', s.occurred_at, true
    from raw.inventory_movements_stream s
    where s.movement_id not in (select movement_id from analytics.fact_inventory_movement
                                where source_system = 'retail')
),
agora as (select max(occurred_at) as instante from livro),
lote as (select max(occurred_at) as instante from livro where not quente),
pares as (
    select l.source_system, l.armazem, l.produto,
           sum(l.quantity_delta) as fisico,
           coalesce(sum(l.quantity_delta) filter (where not l.quente), 0) as do_lote,
           coalesce(sum(l.quantity_delta) filter (where l.quente), 0) as do_fluxo,
           count(*) filter (where l.quente) as eventos_do_fluxo,
           max(l.occurred_at) as ultimo,
           sum(l.quantity_out) filter (where l.is_sale and l.occurred_at >= (select instante from agora) - make_interval(days => :janela_de_cobertura)) as vendidas,
           coalesce(sum(l.quantity_out) filter (where not l.quente and l.is_sale
               and l.occurred_at >= (select instante from lote) - make_interval(days => :janela_do_ponto)), 0) as vendidas_do_ponto
    from livro l
    group by 1, 2, 3
)
select w.warehouse_name, w.warehouse_region, p.sku, p.product_name, p.leaf_category_name as category_name,
       p.brand_name, pr.fisico::integer as quantity_on_hand,
       coalesce(b.quantity_reserved, 0)::integer as quantity_reserved,
       (pr.fisico - coalesce(b.quantity_reserved, 0))::integer as quantity_available,
       pr.do_lote::integer as quantity_from_batch, pr.do_fluxo::integer as quantity_from_stream,
       pr.eventos_do_fluxo as stream_movement_count,
       ceil(pr.vendidas_do_ponto * (:prazo_de_reposicao + :margem_de_seguranca) / cast(:janela_do_ponto as numeric))::integer as reorder_point,
       (pr.fisico - coalesce(b.quantity_reserved, 0)) <= 0 as is_stockout,
       round(pr.vendidas / cast(:janela_de_cobertura as numeric), 3) as daily_demand_units,
       case when pr.vendidas > 0
            then round((pr.fisico - coalesce(b.quantity_reserved, 0)) / (pr.vendidas / cast(:janela_de_cobertura as numeric)), 1) end as days_of_cover,
       pr.ultimo as last_movement_at
from pares pr
join analytics.dim_warehouse w on w.source_system = pr.source_system and w.warehouse_natural_key = pr.armazem
join analytics.dim_product p on p.source_system = pr.source_system and p.product_natural_key = pr.produto and p.is_current
left join trusted.inventory_balances b on b.source_system = pr.source_system
      and b.warehouse_id = pr.armazem and b.product_variant_id = pr.produto
where pr.fisico - coalesce(b.quantity_reserved, 0)
      < ceil(pr.vendidas_do_ponto * (:prazo_de_reposicao + :margem_de_seguranca) / cast(:janela_do_ponto as numeric))
