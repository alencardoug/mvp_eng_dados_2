-- Invariante 19 — o código de retorno do adquirente segue o resultado (F22 da fila do Bloco 5R).
--
-- A aprovada, a pendente e a recusada têm conjuntos de códigos que não se
-- cruzam. O mapa é o do gerador (`geracao.yml`, `payment_transactions`,
-- `codigo_de_retorno`), espelhado em `vars`; um teste do `pytest` confere que
-- são iguais. Vale nas duas origens. Sobre o dado de antes do ciclo do Bloco
-- 5R este teste falha por desenho.

{% set mapa = var("gateway_codes_by_result") %}

select
    t.source_system,
    t.payment_transaction_id,
    t.transaction_result,
    t.gateway_response_code
from {{ ref('payment_transactions') }} t
where not (
    {%- for resultado, codigos in mapa.items() %}
    (t.transaction_result = '{{ resultado }}' and t.gateway_response_code in ('{{ codigos | join("', '") }}'))
    {%- if not loop.last %} or{% endif %}
    {%- endfor %}
)
