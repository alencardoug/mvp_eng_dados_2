-- P09, referência. Aprovação = autorizações aprovadas ÷ tentativas de autorização, no mês da
-- tentativa, por meio e parcelamento. O capturado de cada pagamento vai para o grupo da sua
-- primeira autorização aprovada (D67).
with tentativas as (
    select f.* from analytics.fact_payment_transaction f where f.transaction_type = 'authorization'
),
primeira_aprovada as (
    select distinct on (source_system, payment_id) source_system, payment_id, payment_transaction_id
    from tentativas where approved_authorization_count = 1
    order by source_system, payment_id, occurred_at, payment_transaction_id
),
capturado as (
    select source_system, payment_id, sum(captured_amount) as capturado
    from analytics.fact_payment_transaction where transaction_type = 'capture'
    group by 1, 2
)
select d.year_month, d.year_number, d.month_number, pm.payment_method_name, pm.method_type,
       t.installments, t.is_instalment_plan,
       sum(t.authorization_count) as authorization_attempt_count,
       sum(t.approved_authorization_count) as approved_authorization_count,
       round(100.0 * sum(t.approved_authorization_count) / nullif(sum(t.authorization_count), 0), 2) as approval_rate_pct,
       sum(t.authorized_amount) as authorized_amount,
       coalesce(sum(c.capturado) filter (where pa.payment_transaction_id is not null), 0) as captured_amount
from tentativas t
join analytics.dim_date d on d.date_key = t.date_key
join analytics.dim_payment_method pm on pm.payment_method_key = t.payment_method_key
left join primeira_aprovada pa on pa.source_system = t.source_system and pa.payment_transaction_id = t.payment_transaction_id
left join capturado c on c.source_system = t.source_system and c.payment_id = t.payment_id
group by 1, 2, 3, 4, 5, 6, 7
