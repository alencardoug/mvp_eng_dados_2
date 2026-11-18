-- F31, regra 1 (D93; plano da reabertura, Bloco 2, item 4): nenhum movimento de estoque depois do corte.
--
-- O `make stream-produce` grava eventos na origem com a data do relógio, depois da `as_of_date`, e o
-- ciclo de 17/11/2026 os levou à P08, à P11 e à P12 da `v2.1.0` (Achados, F31). O exercício de
-- *streaming* roda antes da regeneração, sobre o estado que ela descarta; o estado publicado não tem
-- nenhum. O eixo é o tempo de negócio (`occurred_at`) contra o fim do período do gerador, a meia-noite
-- da `as_of_date` em São Paulo — nunca o registro nem a ingestão.
--
-- Falha por desenho no armazém da `v2.1.0` (o controle positivo, fase (i): 2.200 no varejo, medido em
-- 18/11/2026) e durante o exercício (fase (ii)). Depois da regeneração, é condição de publicação.

select source_system, movement_id, movement_type, occurred_at
from {{ ref('fact_inventory_movement') }}
where occurred_at > {{ meia_noite(var("as_of_date")) }}
