{{ config(tags=['legado_reconciliacao']) }}

-- Depende da quarentena, como a invariante 8.

-- Invariante 20 — nenhuma saída de estoque é coberta por ajuste criado para ela (V4 das Pendências).
--
-- O gerador criava um `adjustment_in` um minuto antes de cada saída sem lastro
-- (`AJU-CONFERENCIA`, com a chave `corrige` no metadado do evento); agora o
-- lastro vem do estoque de abertura, um por par armazém × SKU. Aqui: nenhum
-- ajuste desses no livro; no máximo uma abertura por par, no começo do período
-- e na versão 1 do par; e o saldo corrido do par nunca negativo.
--
-- **Só a carga histórica**, até o corte inclusive: o gerador limita os eventos
-- ao fim do período, e há movimento exatamente nele. O caminho quente escreve
-- depois do corte, com as regras do produtor de eventos, e não é o que a V4
-- corrige. No legado, o saldo corrido negativo só é tolerado no par que tem
-- movimento rejeitado. A exceção é larga, e fica declarado: ela não distingue
-- a entrada rejeitada antes do déficit, que o explica, da saída ou da entrada
-- posterior, que não — a quantidade e a versão podem ser justamente os campos
-- rejeitados. Cada par exonerado é conferido um a um no ciclo. Sobre o dado de antes
-- do ciclo do Bloco 5R este teste falha por desenho.

{% set as_of = meia_noite(var("as_of_date")) %}
{% set inicio = meia_noite(var("period_start")) %}

with livro as (

    select
        m.*,
        sum(m.quantity_delta) over (
            partition by m.source_system, m.warehouse_id, m.product_variant_id
            order by m.aggregate_version
        ) as running_balance
    from {{ ref('inventory_movements') }} m
    where m.occurred_at <= {{ as_of }}

)

select source_system, warehouse_id, product_variant_id, source_id, 'adjustment created to back an outbound movement' as violation
from livro
where source_id = 'AJU-CONFERENCIA'
   or event_metadata like '%"corrige"%'

union all

select source_system, warehouse_id, product_variant_id, 'ESTOQUE-INICIAL', 'more than one opening for the pair'
from livro
where source_id = 'ESTOQUE-INICIAL'
group by source_system, warehouse_id, product_variant_id
having count(*) > 1

union all

select source_system, warehouse_id, product_variant_id, 'ESTOQUE-INICIAL', 'opening outside the start of the period'
from livro
where source_id = 'ESTOQUE-INICIAL'
  and (occurred_at <> {{ inicio }} or aggregate_version <> 1)

union all

select distinct l.source_system, l.warehouse_id, l.product_variant_id, cast(null as {{ tipo_texto() }}), 'negative running balance'
from livro l
where l.running_balance < 0
  and not {{ explicado_pela_quarentena('inventory_movements', ['warehouse_id', 'product_variant_id'], 'l') }}
