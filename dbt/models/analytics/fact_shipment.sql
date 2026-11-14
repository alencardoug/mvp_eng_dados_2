-- Fato de remessa — o grão é a remessa (ADR-0053, D66).
--
-- ── Por que uma fato no grão da remessa, ao lado da de item ────────────────
-- A pontualidade, a transportadora, a modalidade e a promessa de prazo são
-- atributos da **remessa** (ADR-0033). Até aqui a P13 os lia de
-- `fact_shipment_item`, reduzindo os itens a remessa com `distinct`, e a remessa
-- cujos itens foram todos rejeitados não tinha linha para reduzir: no legado,
-- 16 das 147 remessas entregues ficavam de fora, todas com os itens na
-- quarentena por defeito do produto, três níveis acima (D66). A remessa passou
-- pelas regras; o que se rejeitou foi o conteúdo. Aqui ela tem a sua linha.
--
-- A fato de item continua: é ela que diz **o que** foi enviado. A P14 também lê
-- esta fato desde a auditoria das views (F17), pela remessa que fecha o ciclo. Os atributos de remessa e de pedido saem dos mesmos
-- modelos de `trusted` e com as mesmas expressões, para as duas fatos não
-- divergirem. Nenhum teste compara as duas fatos atributo a atributo: esta se
-- reconcilia com `shipments` (contagem e tentativas de entrega), a de item com
-- `shipment_items` (contagem e unidades), e o limite está no Modelo de Dados §3.

with remessas as {{ 'not materialized ' if target.type == 'postgres' else '' }}(

    select * from {{ ref('shipments') }}

),

pedidos as (

    select * from {{ ref('orders') }}

),

ciclo as (

    select
        source_system,
        order_id,
        count(*)                                        as order_shipment_count,
        {{ contar_onde("is_delivered") }}            as delivered_shipment_count,
        {{ bool_and('is_delivered') }}                          as is_order_cycle_closed,
        {{ agregado_onde('max', "delivered_at", "is_delivered") }}   as order_delivered_at
    from remessas
    group by source_system, order_id

),

fechamento as (

    select
        source_system,
        shipment_id,
        row_number() over (
            partition by source_system, order_id
            order by delivered_at desc, shipment_id desc
        ) = 1                                           as is_cycle_closing_shipment
    from remessas
    where is_delivered

),

base as (

    select
        r.source_system,
        r.shipment_id,
        r.order_id,
        r.shipment_code,
        r.carrier_id,
        r.warehouse_id,
        r.shipment_status,
        r.tracking_code,
        r.shipped_at,
        r.estimated_delivery_at,
        r.delivered_at,
        r.returned_at,
        r.is_delivered,
        r.is_dispatched,
        r.is_returned,
        r.is_lost,
        r.is_on_time,
        r.delivery_delay_days,
        r.transit_days,
        r.failed_attempt_count,
        {{ data_em_sao_paulo('coalesce(r.shipped_at, r.source_created_at)') }}
                                                        as shipment_date,
        {{ data_em_sao_paulo('r.delivered_at') }}
                                                        as delivered_date,
        p.customer_id,
        p.sales_channel_id,
        p.order_number,
        p.order_status,
        p.placed_at,
        c.order_shipment_count,
        c.delivered_shipment_count,
        c.is_order_cycle_closed,
        c.order_delivered_at,
        coalesce(f.is_cycle_closing_shipment, false)    as is_cycle_closing_shipment,
        {% call decimal_fixo(12, 4) %}case
            when c.is_order_cycle_closed
            then {{ dias_entre('c.order_delivered_at', 'p.placed_at') }}
        end{% endcall %}                             as order_to_delivery_days
    from remessas r
    join pedidos p
        on p.source_system = r.source_system and p.order_id = r.order_id
    join ciclo c
        on c.source_system = r.source_system and c.order_id = r.order_id
    left join fechamento f
        on f.source_system = r.source_system and f.shipment_id = r.shipment_id

)

select
    {{ dbt_utils.generate_surrogate_key(['b.source_system', 'b.shipment_id']) }}
                                                    as shipment_key,
    b.source_system,
    d.date_key,
    dd.date_key                                         as delivered_date_key,
    cr.carrier_key,
    w.warehouse_key,
    cu.customer_key,
    ch.sales_channel_key,
    coalesce(g.geography_key, {{ chave_desconhecida() }}) as geography_key,
    b.shipment_id,
    b.order_id,
    b.shipment_code,
    b.order_number,
    b.tracking_code,
    b.shipment_status,
    b.order_status,
    b.placed_at,
    b.shipped_at,
    b.estimated_delivery_at,
    b.delivered_at,
    b.returned_at,
    b.is_dispatched,
    b.is_delivered,
    b.is_returned,
    b.is_lost,
    b.is_on_time,
    b.order_shipment_count,
    b.delivered_shipment_count,
    b.is_order_cycle_closed,
    b.is_cycle_closing_shipment,
    b.order_shipment_count > 1                          as is_split_order,
    b.order_delivered_at,
    b.order_to_delivery_days,
    b.failed_attempt_count,
    b.delivery_delay_days,
    b.transit_days
from base b
join {{ ref('dim_date') }} d on d.full_date = b.shipment_date
left join {{ ref('dim_date') }} dd on dd.full_date = b.delivered_date
join {{ ref('dim_carrier') }} cr
  on cr.source_system = b.source_system and cr.carrier_natural_key = b.carrier_id
join {{ ref('dim_warehouse') }} w
  on w.source_system = b.source_system and w.warehouse_natural_key = b.warehouse_id
join {{ ref('dim_sales_channel') }} ch
  on ch.source_system = b.source_system
 and ch.sales_channel_natural_key = b.sales_channel_id
join {{ ref('dim_customer') }} cu
  on cu.source_system = b.source_system
 and cu.customer_natural_key = b.customer_id
 and b.placed_at >= cu.valid_from
 and (cu.valid_to is null or b.placed_at < cu.valid_to)
left join {{ ref('dim_geography') }} g
  on g.country = cu.country and g.state_code = cu.state_code and g.city = cu.city
