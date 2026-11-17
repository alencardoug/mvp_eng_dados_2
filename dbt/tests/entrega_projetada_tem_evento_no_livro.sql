{{ config(tags=['legado_reconciliacao']) }}

-- Depende da quarentena, como a invariante 8: a exceção tolerada precisa da
-- contrapartida, e a DAG constrói `quarantine` depois de `trusted`.

-- A entrega que a origem projeta existe no livro.
--
-- O [ADR-0034](../../docs/adr/0034-entrega-do-livro-de-eventos.md) fez do livro
-- `delivery_events` a fonte da data de entrega, e a coluna
-- `shipments.delivered_at` a conferência. Este é o ato de conferir.
--
-- Remessa que a origem diz entregue sem evento `delivered` correspondente não
-- é contada como entregue **e não é descartada**: ela está em
-- `quarantine.rejected_shipment_deliveries` com código e motivo. Este teste
-- falha quando isso acontece — não porque a quarentena seja proibida, mas
-- porque uma divergência entre as duas fontes é achado que alguém precisa
-- olhar, e não estado normal de operação.
--
-- **A exceção do legado** (Q62 do plano da base dos consumidores, 16/11/2026):
-- a falha deliberada do catálogo pode rejeitar o próprio evento `delivered` —
-- foi o `DATE_FUTURE` na remessa 45 do lote do Bloco 5R. Aí a divergência tem
-- contrapartida, e é tolerada só onde a quarentena do tratamento corrente tem
-- um evento `delivered` rejeitado **daquela** remessa (a macro das invariantes
-- 8 e 17, com o tipo do evento). Mensagem, tentativa ou qualquer outro evento
-- rejeitado não explica nada; no varejo não há exceção.
--
-- Lê a mesma definição do modelo de rejeição (`is_delivery_unbacked`, em
-- `trusted.shipments`) e não a tabela da quarentena, porque ela não guarda a
-- origem, e o `shipment_id` se repete entre as duas.

with sem_evento as (

    select
        s.source_system,
        s.shipment_id,
        s.shipment_code,
        s.delivered_at_projected,
        -- O tipo do evento que a quarentena precisa ter para explicar a falta.
        'delivered' as event_type
    from {{ ref('shipments') }} s
    where s.is_delivery_unbacked

)

select
    source_system,
    shipment_id,
    shipment_code,
    'DELIVERY_WITHOUT_EVENT' as rejection_code,
    delivered_at_projected
from sem_evento e
where not (
    e.source_system = 'legacy'
    and {{ explicado_pela_quarentena('delivery_events', ['shipment_id', 'event_type'], 'e') }}
)
