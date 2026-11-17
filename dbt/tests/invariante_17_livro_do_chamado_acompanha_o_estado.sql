{{ config(tags=['legado_reconciliacao']) }}

-- Depende da quarentena, como a invariante 8: a exceção tolerada precisa da
-- contrapartida, e a DAG constrói `quarantine` depois de `trusted`.

-- Invariante 17 — o livro do chamado acompanha o estado dele (F26 da fila do Bloco 5R).
--
-- Todo chamado `resolved` ou `closed` tem o evento `resolved`; todo `reopened`
-- vem depois de um `resolved`, e o chamado reaberto está `in_progress`;
-- `closed_at` é preenchido exatamente no `closed`.
--
-- No legado, o evento de resolução pode ter ido para a quarentena (o pai
-- sobrevive à rejeição do filho, D35): a falta dele só é tolerada onde a
-- quarentena tem um evento **`resolved`** rejeitado daquele chamado — uma
-- mensagem rejeitada não explica resolução nenhuma. O que a exceção não
-- alcança, e fica declarado: ela não compara o instante do evento rejeitado
-- com o da reabertura, porque a data pode ser justamente o campo rejeitado; e
-- o evento rejeitado por ter o próprio tipo corrompido não é reconhecido, e
-- acusa. Cada chamado exonerado é conferido um a um no ciclo. Sobre o dado de antes do ciclo do Bloco 5R este teste
-- falha por desenho.

with chamados as (

    select
        t.*,
        t.support_ticket_id as ticket_id,
        -- O tipo do evento que a quarentena precisa ter para explicar a falta.
        'resolved' as event_type
    from {{ ref('support_tickets') }} t

),

reaberturas as (

    select
        e.source_system,
        e.support_ticket_id,
        {{ contar_onde('not exists (
            select 1 from ' ~ ref('ticket_events') ~ ' r
            where r.source_system = e.source_system
              and r.support_ticket_id = e.support_ticket_id
              and r.is_resolution and r.occurred_at < e.occurred_at)') }} as reopenings_without_resolution
    from {{ ref('ticket_events') }} e
    where e.is_reopening
    group by e.source_system, e.support_ticket_id

)

select t.source_system, t.support_ticket_id, t.ticket_status, 'resolved or closed without the resolved event' as violation
from chamados t
where t.ticket_status in ('resolved', 'closed')
  and t.first_resolved_at is null
  and not {{ explicado_pela_quarentena('ticket_events', ['ticket_id', 'event_type'], 't') }}

union all

select t.source_system, t.support_ticket_id, t.ticket_status, 'reopened without a resolved event before'
from chamados t
join reaberturas r
    on r.source_system = t.source_system and r.support_ticket_id = t.support_ticket_id
where r.reopenings_without_resolution > 0
  and not {{ explicado_pela_quarentena('ticket_events', ['ticket_id', 'event_type'], 't') }}

union all

select t.source_system, t.support_ticket_id, t.ticket_status, 'reopened and not in progress'
from chamados t
join reaberturas r
    on r.source_system = t.source_system and r.support_ticket_id = t.support_ticket_id
where t.ticket_status <> 'in_progress'

union all

select t.source_system, t.support_ticket_id, t.ticket_status, 'closed_at does not match the closed status'
from chamados t
where (t.closed_at is not null) <> (t.ticket_status = 'closed')
