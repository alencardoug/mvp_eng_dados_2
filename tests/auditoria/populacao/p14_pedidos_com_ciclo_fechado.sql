-- P14: os pedidos da view são os de `trusted` com todas as remessas entregues, inclusive o de
-- itens rejeitados em cascata (antes da correção da auditoria, 13 pedidos do legado a menos).
with camada as (
    select count(*) as n
    from (select source_system, order_id from trusted.shipments group by 1, 2 having bool_and(is_delivered)) p
)
select c.n, (select sum(order_count) from consumption.order_to_delivery_time_by_region)
from camada c
where c.n is distinct from (select sum(order_count) from consumption.order_to_delivery_time_by_region)
