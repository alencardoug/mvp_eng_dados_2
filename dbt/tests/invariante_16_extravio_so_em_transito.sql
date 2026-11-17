-- Invariante 16 — remessa `lost` é de pedido `shipped` (F25 da fila do Bloco 5R).
--
-- O extravio não convive com o pedido entregue: o pedido diria que chegou, e a
-- remessa dele, que se perdeu. Vale nas duas origens. Sobre o dado de antes do
-- ciclo do Bloco 5R este teste falha por desenho.

select
    s.source_system,
    s.shipment_id,
    s.order_id,
    o.order_status
from {{ ref('shipments') }} s
join {{ ref('orders') }} o
    on o.source_system = s.source_system and o.order_id = s.order_id
where s.shipment_status = 'lost'
  and o.order_status <> 'shipped'
