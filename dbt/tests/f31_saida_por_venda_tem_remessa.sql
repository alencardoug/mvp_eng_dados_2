{{ config(tags=['fronteira']) }}

-- Lê `analytics` (as fatos) e `quarantine` (a contrapartida do legado), que a DAG constrói em tarefas
-- diferentes: roda na tarefa `dbt_fronteiras`, com tudo construído (`tests/test_dbt.py`).
-- F31, regra 2 (D93; plano da reabertura, Bloco 2, item 4): toda saída por venda tem a remessa dela.
--
-- O vínculo é o que o gerador grava: `source_type = 'sale'` e `source_id` igual ao `shipment_code` de
-- uma remessa da mesma origem. Não há chave estrangeira de movimento para remessa. Transferência,
-- devolução e ajuste ficam fora da exigência.
--
-- **No varejo, sem exceção**: é onde o produtor de eventos escreve, e a venda que ele emite não tem
-- pedido nem remessa (984 no armazém da `v2.1.0`, medido em 18/11/2026). **No legado** (Q72 (d)), passa
-- a venda cuja remessa está na quarentena da captura e do tratamento correntes com o código intacto —
-- a remessa rejeitada em cascata, como as 13 da `v2.1.0` — e a que o Owner aceitou na lista
-- `f31_legacy_sale_exceptions`, no mesmo recorte. Qualquer outra reprova: um caso novo não passa em
-- silêncio.

with sem_remessa as (

    select m.source_system, m.movement_id, m.source_id as shipment_code, m.occurred_at
    from {{ ref('fact_inventory_movement') }} m
    left join {{ ref('fact_shipment') }} s
      on  s.source_system = m.source_system
      and s.shipment_code = m.source_id
    where m.source_type = 'sale'
      and s.shipment_code is null

),

corrente as (

    select distinct source_system, snapshot_id, catalog_version, treatment_fingerprint
    from {{ ref('legacy_classifications') }}

)

select v.source_system, v.movement_id, v.shipment_code, v.occurred_at
from sem_remessa v
where v.source_system = 'retail'
   or (
        v.source_system = 'legacy'
    and not {{ explicado_pela_quarentena('shipments', ['shipment_code'], 'v') }}
    and not exists (
            select 1
            from {{ ref('f31_legacy_sale_exceptions') }} x
            join corrente c
              on  c.source_system = 'legacy'
              and c.snapshot_id = x.snapshot_id
              and c.catalog_version = x.catalog_version
              and c.treatment_fingerprint = x.treatment_fingerprint
            where x.movement_id = cast(v.movement_id as {{ tipo_texto() }})
              and x.source_id = v.shipment_code
        )
   )
