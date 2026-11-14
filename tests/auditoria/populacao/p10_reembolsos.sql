-- P10: o reembolsado da view é o dos reembolsos concluídos de `trusted`, e a contagem é a de
-- todos os reembolsos (totais; o mês do reembolso é o da fato, F14).
select (select sum(refund_amount) from trusted.refunds where is_completed) as na_camada,
       (select sum(refunded_amount) from consumption.refund_rate_by_reason) as na_view,
       (select count(*) from trusted.refunds) as reembolsos_na_camada,
       (select sum(refund_count) from consumption.refund_rate_by_reason) as reembolsos_na_view
where (select sum(refund_amount) from trusted.refunds where is_completed)
      is distinct from (select sum(refunded_amount) from consumption.refund_rate_by_reason)
   or (select count(*) from trusted.refunds) is distinct from (select sum(refund_count) from consumption.refund_rate_by_reason)
