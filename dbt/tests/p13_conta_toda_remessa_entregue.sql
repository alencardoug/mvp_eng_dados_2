{{ config(tags=['fronteira']) }}

-- Lê `trusted` ao lado de `consumption`: atravessa camadas, por isso é `fronteira`.

-- A P13 conta toda remessa entregue (ADR-0033, ADR-0053): o denominador é a
-- população de `trusted.shipments`, e não a das remessas que têm item aceito.
-- Por mês da chegada, a view tem de somar o mesmo número de remessas
-- entregues que a camada responsável. A versão que lia `fact_shipment_item`
-- perdia 16 remessas do legado aqui (D66).

with na_camada as (

    select
        d.year_month,
        count(*)                                    as remessas_entregues
    from {{ ref('shipments') }} s
    join {{ ref('dim_date') }} d
      on d.full_date = {{ data_em_sao_paulo('s.delivered_at') }}
    where s.is_delivered
    group by 1

),

na_view as (

    -- A view não expõe a origem; o total do mês soma as duas.
    select
        year_month,
        sum(delivered_count)                        as remessas_entregues
    from {{ ref('on_time_delivery_rate_by_carrier') }}
    group by 1

)

select
    coalesce(c.year_month, v.year_month)            as year_month,
    c.remessas_entregues                            as na_camada,
    v.remessas_entregues                            as na_view
from na_camada c
full outer join na_view v
  on v.year_month = c.year_month
where c.remessas_entregues is distinct from v.remessas_entregues
