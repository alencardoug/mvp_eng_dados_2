{{ config(tags=['fronteira']) }}

-- Lê `staging`, `trusted` e a quarentena: atravessa tarefas da DAG, e por isso
-- leva a etiqueta `fronteira` e roda em `dbt_fronteiras`, depois de todas as
-- camadas (Qualidade §7).

-- Invariante 18 — toda reserva é de um item do carrinho ou do pedido dela (F27 da fila do Bloco 5R).
--
-- O mesmo SKU e a mesma quantidade de um item da origem da reserva, no máximo
-- uma reserva por item, num armazém que movimentou o SKU. É uma relação a
-- mais: a invariante 8 trata do saldo, não da origem.
--
-- A tabela das reservas não tem modelo próprio em `trusted`: lê-se o
-- `staging` do varejo e os aptos do legado, as duas relações que
-- `inventory_balances` empilha. No legado, o item rejeitado explica a reserva
-- **sem item nenhum daquele SKU** na origem dela — se o item apto existe e a
-- quantidade é outra, uma duplicata rejeitada não explica nada, e a guarda
-- acusa —, e o movimento rejeitado explica o armazém sem movimento nenhum do
-- SKU. Sobre o dado de
-- antes do ciclo do Bloco 5R este teste falha por desenho.

with reservas as (

    select 'retail' as source_system, stock_reservation_id, warehouse_id, product_variant_id,
           cart_id, order_id, quantity_reserved
    from {{ ref('stg_retail__stock_reservations') }}
    where not is_deleted
    union all
    select 'legacy' as source_system, stock_reservation_id, warehouse_id, product_variant_id,
           cart_id, order_id, quantity_reserved
    from {{ ref('legado__stock_reservations') }}
    where not is_deleted

),

itens as (

    select 'retail' as source_system, cart_id, cast(null as bigint) as order_id, product_variant_id, quantity
    from {{ ref('stg_retail__cart_items') }}
    where not is_deleted
    union all
    select 'legacy' as source_system, cart_id, cast(null as bigint), product_variant_id, quantity
    from {{ ref('legado__cart_items') }}
    where not is_deleted
    union all
    select source_system, cast(null as bigint), order_id, product_variant_id, quantity
    from {{ ref('order_items') }}
    where not is_deleted

),

conferidas as (

    select
        r.*,
        exists (
            select 1 from itens i
            where i.source_system = r.source_system
              and i.product_variant_id = r.product_variant_id
              and i.quantity = r.quantity_reserved
              and (i.cart_id = r.cart_id or i.order_id = r.order_id)
        ) as has_item,
        exists (
            select 1 from itens i
            where i.source_system = r.source_system
              and i.product_variant_id = r.product_variant_id
              and (i.cart_id = r.cart_id or i.order_id = r.order_id)
        ) as has_sku_in_origin,
        count(*) over (
            partition by r.source_system, r.cart_id, r.order_id, r.product_variant_id
        ) as reservations_of_the_item,
        exists (
            select 1 from {{ ref('inventory_movements') }} m
            where m.source_system = r.source_system
              and m.warehouse_id = r.warehouse_id
              and m.product_variant_id = r.product_variant_id
        ) as has_movement
    from reservas r

)

select source_system, stock_reservation_id, cart_id, order_id, product_variant_id, 'no item of its origin with the SKU and the quantity' as violation
from conferidas c
where not has_item
  and (
      has_sku_in_origin
      or (
          not {{ explicado_pela_quarentena('cart_items', ['cart_id', 'product_variant_id'], 'c') }}
          and not {{ explicado_pela_quarentena('order_items', ['order_id', 'product_variant_id'], 'c') }}
      )
  )

union all

select source_system, stock_reservation_id, cart_id, order_id, product_variant_id, 'item reserved more than once'
from conferidas
where reservations_of_the_item > 1

union all

select source_system, stock_reservation_id, cart_id, order_id, product_variant_id, 'warehouse without movement of the SKU'
from conferidas c
where not has_movement
  and not {{ explicado_pela_quarentena('inventory_movements', ['warehouse_id', 'product_variant_id'], 'c') }}
