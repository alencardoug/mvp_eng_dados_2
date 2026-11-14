-- P13 — Qual a fração de entregas dentro do prazo prometido, por transportadora
-- e modalidade, mês a mês?
--
-- **Grão da remessa** ([ADR-0033](../../../docs/adr/0033-entrega-medida-em-dois-graos.md)):
-- transportadora e modalidade são atributos da remessa, e é nela que a promessa
-- de prazo existe. O pedido dividido em duas remessas conta **duas vezes** aqui,
-- de propósito — foram duas promessas e duas chegadas.
--
-- O mês é o da **chegada**, não o do despacho: a pergunta é sobre entregas
-- realizadas, e uma remessa que saiu em janeiro e chegou em fevereiro é uma
-- entrega de fevereiro.
--
-- A fato é a da remessa (ADR-0053, D66): uma linha por remessa, inclusive a
-- que não tem item aceito. Até 14/11/2026 a view reduzia `fact_shipment_item`
-- a remessa com `distinct`, e a remessa cujos itens foram todos rejeitados em
-- cascata não tinha linha para reduzir: no legado, 16 das 147 remessas
-- entregues ficavam de fora.

with remessas as (

    select
        f.source_system,
        f.shipment_id,
        f.delivered_date_key,
        f.carrier_key,
        f.warehouse_key,
        f.is_on_time,
        f.is_split_order,
        f.delivery_delay_days,
        f.transit_days,
        f.failed_attempt_count
    from {{ ref('fact_shipment') }} f
    where f.is_delivered

)

select
    d.year_number,
    d.month_number,
    d.year_month,
    c.carrier_name,
    c.service_level,
    w.warehouse_name,
    w.warehouse_region,

    count(*)                                                as delivered_count,
    {{ contar_onde("r.is_on_time") }}                    as on_time_count,
    {{ contar_onde("not r.is_on_time") }}                as late_count,
    {{ contar_onde("r.is_split_order") }}                as split_order_shipment_count,

    -- Não aditiva: recalcula-se a cada recorte, e nunca se soma entre linhas.
    round(
        cast({{ contar_onde("r.is_on_time") }} as numeric) / nullif(count(*), 0), 4
    )                                                       as on_time_rate,

    -- Positivo é atraso, negativo é adiantamento. A média sobre as atrasadas
    -- responde "quando atrasa, atrasa quanto" — pergunta diferente de "com que
    -- frequência atrasa", e as duas juntas é que descrevem a transportadora.
    round({{ agregado_onde('avg', "r.delivery_delay_days", "not r.is_on_time") }}, 4)
                                                            as avg_delay_days_when_late,
    round(avg(r.transit_days), 4)                           as avg_transit_days,
    -- `sum` de bigint é `numeric` no PostgreSQL e INT64 no BigQuery: o contrato diz numeric.
    cast(sum(r.failed_attempt_count) as numeric)            as failed_attempt_count
from remessas r
join {{ ref('dim_date') }} d on d.date_key = r.delivered_date_key
join {{ ref('dim_carrier') }} c on c.carrier_key = r.carrier_key
join {{ ref('dim_warehouse') }} w on w.warehouse_key = r.warehouse_key
group by 1, 2, 3, 4, 5, 6, 7
