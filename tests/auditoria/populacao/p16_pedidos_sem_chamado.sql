-- P16: os pedidos sem chamado da view são os pedidos realizados de `trusted` com a janela fechada,
-- com item aceito e sem chamado. Os com chamado aparecem uma vez por categoria, o que a descrição
-- da coluna declara, e por isso não se somam aqui. Recorte declarado (D35): pedido sem item aceito.
with camada as (
    select count(*) as n
    from trusted.orders o
    where o.is_realised and o.is_repeat_window_closed
      and exists (select 1 from trusted.order_items i where i.source_system = o.source_system and i.order_id = o.order_id)
      and not exists (select 1 from trusted.support_tickets t where t.source_system = o.source_system and t.order_id = o.order_id)
)
select c.n, (select sum(order_count) from consumption.repeat_purchase_rate_after_support where not has_support_ticket)
from camada c
where c.n is distinct from (select sum(order_count) from consumption.repeat_purchase_rate_after_support where not has_support_ticket)
