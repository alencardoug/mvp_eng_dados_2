{{ config(tags=['fronteira']) }}

-- Lê `trusted` e a quarentena ao lado de `analytics`: atravessa camadas, por
-- isso leva a etiqueta `fronteira` e roda em `dbt_fronteiras`.

-- A população de compras da dimensão é a da fato, mais uma exceção declarada
-- (F3 dos Achados do nl_sql).
--
-- `dim_customer` conta os pedidos realizados de `trusted.orders`, no grão do
-- pedido. `fact_sales_order_item` está no grão do item e só tem o pedido que
-- tem item aceito. A D35 preserva o pedido quando os itens dele são rejeitados
-- (ADR-0038): esse pedido existe, foi realizado, e não tem como chegar à fato.
-- Em 14/11/2026 eram 15 pedidos do legado, de 15 clientes, todos com os itens
-- na quarentena; 7 desses clientes têm a primeira compra num deles.
--
-- A regra que este teste guarda: para cada cliente (versão corrente), a
-- contagem e a primeira compra da dimensão são as da fato somadas às desses
-- pedidos — e só desses: pedido realizado sem item aceito e **sem** item na
-- quarentena não é exceção, é defeito, e aparece aqui. A linha devolvida diz o
-- cliente e as duas contas. Sem a exceção, o teste acusaria os 15 clientes.

with na_dimensao as (

    select
        source_system,
        cast(customer_natural_key as {{ dbt.type_string() }})   as cliente,
        order_count,
        first_order_at
    from {{ ref('dim_customer') }}
    where is_current

),

na_fato as (

    select
        f.source_system,
        cast(c.customer_natural_key as {{ dbt.type_string() }}) as cliente,
        {{ contar_distintos(['f.order_id']) }}                  as pedidos,
        min(f.placed_at)                                        as primeira
    from {{ ref('fact_sales_order_item') }} f
    join {{ ref('dim_customer') }} c on c.customer_key = f.customer_key
    where f.is_realised
    group by 1, 2

),

itens_na_quarentena as (

    select distinct
        source_system,
        coalesce(
            {{ campo_json('cleaned_payload', "'order_id'") }},
            {{ campo_json('original_payload', "'order_id'") }}
        )                                                       as order_id
    from {{ ref('rejected_legacy_records') }}
    where source_table = 'order_items'

),

pedidos_sem_item_aceito as (

    -- A exceção declarada: realizado, sem item aceito, com item na quarentena.
    select
        o.source_system,
        cast(o.customer_id as {{ dbt.type_string() }})          as cliente,
        count(*)                                                as pedidos,
        min(o.placed_at)                                        as primeira
    from {{ ref('orders') }} o
    join itens_na_quarentena q
      on q.source_system = o.source_system
     and q.order_id = cast(o.order_id as {{ dbt.type_string() }})
    where o.is_realised
      and not exists (
          select 1
          from {{ ref('order_items') }} i
          where i.source_system = o.source_system
            and i.order_id = o.order_id
      )
    group by 1, 2

)

select
    d.source_system,
    d.cliente,
    d.order_count                                               as pedidos_na_dimensao,
    coalesce(f.pedidos, 0)                                      as pedidos_na_fato,
    coalesce(s.pedidos, 0)                                      as pedidos_sem_item_aceito,
    d.first_order_at                                            as primeira_na_dimensao,
    f.primeira                                                  as primeira_na_fato,
    s.primeira                                                  as primeira_sem_item_aceito
from na_dimensao d
left join na_fato f
       on f.source_system = d.source_system and f.cliente = d.cliente
left join pedidos_sem_item_aceito s
       on s.source_system = d.source_system and s.cliente = d.cliente
-- `is distinct from`, e não `<>`: a contagem nula na dimensão também é acusada.
where d.order_count is distinct from coalesce(f.pedidos, 0) + coalesce(s.pedidos, 0)
   or d.first_order_at is distinct from
      case
          when f.primeira is null then s.primeira
          when s.primeira is null then f.primeira
          when s.primeira < f.primeira then s.primeira
          else f.primeira
      end
