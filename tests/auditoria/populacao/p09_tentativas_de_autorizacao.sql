-- P09: as tentativas da view, por mês, são as transações de autorização de `trusted`.
with camada as (
    select to_char(occurred_at at time zone 'America/Sao_Paulo', 'YYYY-MM') as year_month, count(*) as n
    from trusted.payment_transactions where is_authorization group by 1
),
na_view as (
    select year_month, sum(authorization_attempt_count) as n from consumption.payment_approval_rate_by_method group by 1
)
select coalesce(c.year_month, v.year_month), c.n, v.n
from camada c full outer join na_view v using (year_month)
where c.n is distinct from v.n
