{{ config(tags=['fronteira']) }}

-- Compara camadas que a DAG constrói em tarefas diferentes — as fatos de
-- `analytics` e a view de `consumption` —: só tem o que ler depois da última
-- delas, e por isso leva a etiqueta `fronteira` e roda em `dbt_fronteiras`
-- (airflow/dags/fluxo_batch.py), como o `p09_capturado_reconcilia_com_a_fato`.

-- A P15 conta todos os chamados abertos, e o denominador de cada mês e canal é
-- o de todas as origens (F1 dos Achados do nl_sql).
--
-- Dois lados, cada um calculado das fatos sem passar pela view: os chamados
-- abertos por mês e canal pelo nome, e os pedidos realizados distintos por mês
-- e canal pelo nome. A view tem de dar o mesmo total de chamados em cada mês e
-- canal, e o mesmo denominador em toda linha do canal. A linha devolvida diz
-- onde e quanto. A versão anterior da view, que ligava o denominador pela chave
-- de cada origem, falha aqui nos meses em que o legado vendeu e não teve chamado.

with chamados_na_fato as (

    select
        d.year_month,
        ch.sales_channel_name,
        count(*) as ticket_count
    from {{ ref('fact_support_ticket_event') }} f
    join {{ ref('dim_sales_channel') }} ch on ch.sales_channel_key = f.sales_channel_key
    join {{ ref('dim_date') }} d on d.date_key = f.date_key
    where f.is_ticket_creation
    group by 1, 2

),

pedidos_na_fato as (

    select
        d.year_month,
        ch.sales_channel_name,
        cast({{ contar_distintos(['f.source_system', 'f.order_id']) }} as numeric) as channel_order_count
    from {{ ref('fact_sales_order_item') }} f
    join {{ ref('dim_sales_channel') }} ch on ch.sales_channel_key = f.sales_channel_key
    join {{ ref('dim_date') }} d on d.date_key = f.date_key
    where f.is_realised
    group by 1, 2

),

na_view as (

    select
        year_month,
        sales_channel_name,
        sum(ticket_count)            as ticket_count,
        count(*)                     as linhas,
        -- `min` e `max` ignoram nulo: a contagem dos não nulos é o que acusa uma
        -- linha sem denominador num canal que tem pedidos.
        count(channel_order_count)   as linhas_com_denominador,
        min(channel_order_count)     as menor_denominador,
        max(channel_order_count)     as maior_denominador
    from {{ ref('support_tickets_per_hundred_orders') }}
    group by 1, 2

)

select
    coalesce(v.year_month, c.year_month)                 as year_month,
    coalesce(v.sales_channel_name, c.sales_channel_name) as sales_channel_name,
    c.ticket_count                                       as chamados_na_fato,
    v.ticket_count                                       as chamados_na_view,
    p.channel_order_count                                as pedidos_na_fato,
    v.menor_denominador,
    v.maior_denominador
from na_view v
full outer join chamados_na_fato c
       on c.year_month = v.year_month
      and c.sales_channel_name = v.sales_channel_name
left join pedidos_na_fato p
       on p.year_month = coalesce(v.year_month, c.year_month)
      and p.sales_channel_name = coalesce(v.sales_channel_name, c.sales_channel_name)
where v.ticket_count is distinct from c.ticket_count
   or v.menor_denominador is distinct from p.channel_order_count
   or v.maior_denominador is distinct from p.channel_order_count
   or (p.channel_order_count is not null and v.linhas_com_denominador <> v.linhas)
   or (p.channel_order_count is null and v.linhas_com_denominador <> 0)
