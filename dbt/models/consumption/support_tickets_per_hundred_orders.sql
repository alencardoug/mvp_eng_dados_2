-- P15 — Quantos chamados por 100 pedidos, por categoria de chamado e canal,
-- mês a mês?
--
-- ── Duas fatos, dois grãos, um *drill across* ───────────────────────────────
-- O numerador vem de `fact_support_ticket_event` e o denominador de
-- `fact_order_status_event`. Nenhuma das duas está no grão da resposta: as duas
-- estão no grão do **evento** (do chamado e do pedido), e o denominador usa só o
-- evento de criação de cada pedido realizado. Cada uma é
-- reduzida ao seu grão de contagem antes de se encontrarem — que é o que o
-- ADR-0030 chama de *drill across*, e o motivo de não haver `join` entre fatos
-- aqui.
--
-- ── O denominador é do canal, não da categoria ──────────────────────────────
-- Pedido não tem categoria de chamado, e não faria sentido ter. Por isso a
-- coluna se chama `channel_order_count`, e não `order_count`: ela é do mês e do
-- canal, e **se repete** em cada linha de categoria. Somá-la ao longo das
-- categorias multiplica os pedidos pelo número de categorias — o nome existe
-- para que quem for somar pare antes.
--
-- ── O canal é o do nome, somando as origens ─────────────────────────────────
-- `dim_sales_channel` tem uma linha por canal **e por origem**: "Aplicativo"
-- do `retail` e "Aplicativo" do `legacy` têm chaves diferentes. Agrupar pela
-- chave partia o canal em dois e, pior, ligava o denominador aos chamados pela
-- chave: a origem que não teve chamado naquele mês e categoria perdia os seus
-- pedidos do denominador. Em jan/2024, Conta, Aplicativo, a taxa dava 100/22 e
-- é 100/23 (Achados do nl_sql, F1). Por isso os dois lados são reduzidos ao
-- grão da resposta — mês × canal **pelo nome** — cada um por si, e só então se
-- encontram. A categoria de chamado também vai pelo nome e pelo grupo.
--
-- **O pedido vem do grão do pedido** (`fact_order_status_event`, o evento de
-- criação): o pedido realizado cujos itens foram todos rejeitados em cascata
-- não está na fato de item e saía do denominador — 15 pedidos do legado em
-- 14/11/2026, achado na revisão da auditoria das views, o padrão da D66.

-- ── Duas ausências previstas, e o que cada uma significa ────────────────────
-- **Linha com `channel_order_count` nulo.** São os chamados do canal *Sem
-- canal* — os que não nasceram de pedido. Sem pedido não há canal, e sem canal
-- não há denominador: a contagem aparece e a taxa fica nula, que é a resposta
-- honesta. Foram 45 dos 400 chamados na execução de referência, e **todos** de
-- lá: nenhum canal real ficou sem denominador em mês nenhum.
--
-- **Mês e canal que não aparecem.** A view tem linha onde houve ao menos um
-- chamado. Mês com pedidos e nenhum chamado não vira linha de zero — seriam
-- seis linhas por combinação, uma por categoria, e a view passaria a ser
-- majoritariamente vazio. Quem precisa da grade completa a produz na leitura,
-- contra `dim_date`.
--
-- ── O mês é o da abertura ───────────────────────────────────────────────────
-- Um chamado é contado no mês em que foi **aberto**, e a redução ao evento
-- `created` é o que garante isso. Contar por evento poria o mesmo chamado em
-- dois meses, e contar pelo fechamento diria que o mês passado melhorou porque
-- os chamados dele ainda não fecharam.

with chamados as (

    select
        f.date_key,
        ch.sales_channel_name,
        ch.channel_type,
        cat.support_category_name,
        cat.support_category_group,
        f.support_ticket_id,
        f.ticket_priority,
        f.was_reopened,
        f.is_solved_first_time,
        f.hours_to_resolution
    from {{ ref('fact_support_ticket_event') }} f
    join {{ ref('dim_sales_channel') }} ch on ch.sales_channel_key = f.sales_channel_key
    join {{ ref('dim_support_category') }} cat on cat.support_category_key = f.support_category_key
    where f.is_ticket_creation

),

pedidos as (

    select
        f.date_key,
        ch.sales_channel_name,
        {{ contar_distintos(['f.source_system', 'f.order_id']) }}   as channel_order_count
    from {{ ref('fact_order_status_event') }} f
    join {{ ref('dim_sales_channel') }} ch on ch.sales_channel_key = f.sales_channel_key
    where f.is_order_creation
      and f.is_realised
    group by f.date_key, ch.sales_channel_name

),

pedidos_por_mes as (

    select
        d.year_month,
        p.sales_channel_name,
        -- `sum` de bigint é `numeric` no PostgreSQL e INT64 no BigQuery: o contrato diz numeric.
        cast(sum(p.channel_order_count) as numeric)     as channel_order_count
    from pedidos p
    join {{ ref('dim_date') }} d on d.date_key = p.date_key
    group by d.year_month, p.sales_channel_name

),

chamados_por_mes as (

    select
        d.year_number,
        d.month_number,
        d.year_month,
        c.sales_channel_name,
        c.channel_type,
        c.support_category_name,
        c.support_category_group,
        count(*)                                        as ticket_count,
        {{ contar_onde("c.ticket_priority in ('high', 'urgent')") }}
                                                        as high_priority_ticket_count,
        {{ contar_onde("c.was_reopened") }}          as reopened_ticket_count,
        {{ contar_onde("c.is_solved_first_time") }}  as solved_first_time_count,
        -- A média sai dos chamados do recorte, nunca da média de médias por origem.
        round(avg(c.hours_to_resolution), 2)            as avg_hours_to_resolution
    from chamados c
    join {{ ref('dim_date') }} d on d.date_key = c.date_key
    group by 1, 2, 3, 4, 5, 6, 7

)

select
    t.year_number,
    t.month_number,
    t.year_month,
    t.sales_channel_name,
    t.channel_type,
    t.support_category_name,
    t.support_category_group,

    t.ticket_count,
    t.high_priority_ticket_count,
    t.reopened_ticket_count,
    t.solved_first_time_count,
    p.channel_order_count,

    -- Não aditiva: recalcula-se a cada recorte. Numerador e denominador vão ao
    -- lado, como em toda view de razão do projeto.
    round(t.ticket_count * cast(100.0 as numeric) / nullif(p.channel_order_count, 0), 4)
                                                        as tickets_per_hundred_orders,
    t.avg_hours_to_resolution
from chamados_por_mes t
left join pedidos_por_mes p
       on p.year_month = t.year_month
      and p.sales_channel_name = t.sales_channel_name
