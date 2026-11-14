-- P10, referência. Reembolsado = valor dos reembolsos concluídos, no mês do reembolso, por meio e
-- motivo; contagem de todos os reembolsos; capturado = todo o capturado do mês no meio,
-- repetido em cada motivo.
with reembolsos as (
    select d.year_month, d.year_number, d.month_number, pm.payment_method_name,
           coalesce(f.refund_reason, 'Sem motivo registrado') as refund_reason,
           count(*) as refund_count, sum(f.completed_refund_amount) as refunded_amount
    from analytics.fact_refund f
    join analytics.dim_date d on d.date_key = f.date_key
    join analytics.dim_payment_method pm on pm.payment_method_key = f.payment_method_key
    group by 1, 2, 3, 4, 5
),
capturado as (
    select d.year_month, pm.payment_method_name, sum(t.captured_amount) as capturado
    from analytics.fact_payment_transaction t
    join analytics.dim_date d on d.date_key = t.date_key
    join analytics.dim_payment_method pm on pm.payment_method_key = t.payment_method_key
    group by 1, 2
)
select r.year_month, r.year_number, r.month_number, r.payment_method_name, r.refund_reason,
       r.refund_count, r.refunded_amount, coalesce(c.capturado, 0) as captured_amount,
       round(100.0 * r.refunded_amount / nullif(c.capturado, 0), 2) as refund_rate_pct
from reembolsos r
left join capturado c using (year_month, payment_method_name)
