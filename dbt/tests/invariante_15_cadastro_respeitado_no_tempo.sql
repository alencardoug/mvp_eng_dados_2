{{ config(tags=['fronteira']) }}

-- Lê `staging` (os itens de carrinho, que não têm modelo em `trusted`) e
-- `trusted`: atravessa tarefas da DAG, e por isso leva a etiqueta `fronteira`
-- e roda em `dbt_fronteiras`, depois de todas as camadas (Qualidade §7).

-- Invariante 15 — o estado do cadastro é respeitado no tempo (F24 da fila do Bloco 5R).
--
-- Cliente `pending` ou `blocked` não tem pedido nem carrinho identificado, e
-- produto `draft` não está em item de pedido nem de carrinho. Cliente
-- `inactive`, produto `discontinued` e variante inativa só têm venda anterior
-- à janela que precede o fim do período: o estado é o de hoje, a venda antiga
-- fica, e ninguém "indisponível" vende na véspera do corte.
--
-- As janelas são as do gerador (`geracao.yml`, `orders.processo`), espelhadas
-- em `vars`; um teste do `pytest` confere que são iguais. O instante é o do
-- evento: `placed_at` no pedido e nos itens dele; a conversão, ou a criação,
-- no carrinho; `added_at` no item de carrinho.
--
-- Vale nas duas origens. No legado, o pai rejeitado não chega aqui — a junção
-- não o encontra —, e valor convertido pela limpeza volta ao original. Sobre o
-- dado de antes do ciclo do Bloco 5R este teste falha por desenho.

{% set as_of = meia_noite(var("as_of_date")) %}
{% set corte_cliente = dias_no_calendario(as_of, -var("active_customer_window_days")) %}
{% set corte_variante = dias_no_calendario(as_of, -var("off_sale_window_days")) %}

with itens_de_carrinho as (

    select 'retail' as source_system, cart_item_id, product_variant_id, added_at
    from {{ ref('stg_retail__cart_items') }}
    where not is_deleted
    union all
    select 'legacy' as source_system, cart_item_id, product_variant_id, added_at
    from {{ ref('legado__cart_items') }}
    where not is_deleted

),

compras as (

    select o.source_system, 'order' as origin, o.order_id as origin_id, o.customer_id, o.placed_at as moment
    from {{ ref('orders') }} o
    union all
    select c.source_system, 'cart' as origin, c.cart_id, c.customer_id,
           coalesce(c.cart_converted_at, c.cart_created_at) as moment
    from {{ ref('carts') }} c
    where c.customer_id is not null

),

vendas as (

    select i.source_system, 'order_item' as origin, i.order_item_id as origin_id,
           i.product_variant_id, o.placed_at as moment
    from {{ ref('order_items') }} i
    join {{ ref('orders') }} o
        on o.source_system = i.source_system and o.order_id = i.order_id
    union all
    select source_system, 'cart_item' as origin, cart_item_id, product_variant_id, added_at
    from itens_de_carrinho

)

select c.source_system, c.origin, c.origin_id, k.customer_status as registry_status, c.moment
from compras c
join {{ ref('customers') }} k
    on k.source_system = c.source_system and k.customer_id = c.customer_id
where k.customer_status in ('pending', 'blocked')
   or (k.customer_status = 'inactive' and c.moment >= {{ corte_cliente }})

union all

select v.source_system, v.origin, v.origin_id,
       case when s.variant_is_active then s.product_status else s.product_status || ', inactive variant' end,
       v.moment
from vendas v
join {{ ref('product_skus') }} s
    on s.source_system = v.source_system and s.product_variant_id = v.product_variant_id
where s.product_status = 'draft'
   or ((s.product_status = 'discontinued' or not s.variant_is_active) and v.moment >= {{ corte_variante }})
