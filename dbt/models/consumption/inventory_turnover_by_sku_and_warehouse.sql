-- P11 — Qual o giro de estoque por SKU e armazém no trimestre?
--
-- ── A regra (ADR-0052) ───────────────────────────────────────────────────────
-- Giro = custo do que saiu em venda no trimestre ÷ valor médio do estoque nele.
-- O valor médio é a média, sobre os dias do trimestre, da posição de fim de dia
-- do par (origem, armazém, SKU), valorizada pelo custo médio ponderado das
-- entradas até aquele dia. Nada posterior ao dia entra: nem a quantidade nem o
-- custo. É o princípio do ADR-0030 aplicado ao denominador — uma compra feita
-- hoje não muda o giro de um trimestre fechado.
--
-- A versão anterior usava o saldo **corrente** da projeção vezes a média do
-- custo de todos os movimentos, inclusive os posteriores ao trimestre (F2 dos
-- Achados do nl_sql).
--
-- ── A medida que exige a aditividade declarada ───────────────────────────────
-- `avg_quantity_on_hand` é **semiaditiva**: soma por armazém e por SKU, e
-- **nunca** ao longo do tempo. Somar a média de três trimestres produz um
-- estoque que nunca existiu.
--
-- ── Os dias que contam ───────────────────────────────────────────────────────
-- Do primeiro dia do trimestre — ou do dia do primeiro movimento do par, se ele
-- vier depois — até o fim do trimestre, ou até o último dia do livro daquela
-- origem, se o trimestre ainda não acabou. Tempo de evento, no fuso de São
-- Paulo, pela `dim_date`: nenhum evento atrasado cruza trimestre (o atraso
-- máximo medido é de 900 s).
--
-- ── O que esta média não vê ──────────────────────────────────────────────────
-- O estoque que entra e sai no mesmo dia. O gerador cria uma correção de
-- inventário um minuto antes de toda saída sem lastro (Pendências, V4): nesses
-- pares a posição de fim de dia é zero, e o giro fica indefinido. A posição
-- negativa de um histórico incompleto entra na média como está: o livro é a
-- fonte da verdade. Mas se algum dia tem posição e nenhuma entrada com custo
-- até ele, o valor médio é indefinido (nulo), e o giro também.
--
-- Giro indefinido não é giro zero: sem valor médio positivo, não havia estoque
-- para girar, e o giro é nulo.
--
-- ── Por que a grade é só dos trimestres com venda ────────────────────────────
-- A view responde onde houve saída. Uma grade de todos os dias de todos os
-- pares custaria três milhões de linhas por leitura. Aqui a posição de cada dia
-- é a de abertura do trimestre (a soma de tudo antes dele) mais o acumulado
-- dentro dele — sem junção por intervalo e sem `ignore nulls`, que o PostgreSQL
-- não tem. A abertura cruza só os poucos trimestres com venda com os poucos dias
-- com movimento; a grade não é cruzada com nada.

with movimentos_do_dia as (

    select
        m.source_system,
        w.warehouse_natural_key,
        p.product_natural_key,
        d.full_date                                                     as dia,
        d.year_number,
        d.quarter_number,
        sum(m.quantity_delta)                                           as quantity_delta,
        sum(case when m.is_inbound then m.quantity_in else 0 end)       as inbound_quantity,
        sum(case when m.is_inbound then m.movement_cost_amount else 0 end) as inbound_cost_amount
    from {{ ref('fact_inventory_movement') }} m
    join {{ ref('dim_date') }} d using (date_key)
    join {{ ref('dim_product') }} p using (product_key)
    join {{ ref('dim_warehouse') }} w using (warehouse_key)
    group by 1, 2, 3, 4, 5, 6

),

saidas as (

    select
        d.year_number,
        d.quarter_number,
        p.source_system,
        p.product_natural_key,
        w.warehouse_natural_key,
        p.sku,
        p.product_name,
        cat.category_name,
        w.warehouse_name,
        w.warehouse_region,
        sum(m.quantity_out)                         as quantity_out,
        sum(m.cogs_amount)                          as cost_of_goods_sold
    from {{ ref('fact_inventory_movement') }} m
    join {{ ref('dim_date') }} d using (date_key)
    join {{ ref('dim_product') }} p using (product_key)
    join {{ ref('dim_warehouse') }} w using (warehouse_key)
    -- A categoria casa por (origem, id): sem a origem, cada categoria do legado
    -- encontra também a homônima do retail e o custo se multiplica.
    join {{ ref('dim_category') }} cat
      on  cat.source_system = p.source_system
     and cat.category_natural_key = p.product_category_id
    where m.is_sale
    group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

),

trimestres as (

    select distinct
        source_system, warehouse_natural_key, product_natural_key, year_number, quarter_number
    from saidas

),

limites as (

    select year_number, quarter_number, min(full_date) as primeiro_dia
    from {{ ref('dim_date') }}
    group by 1, 2

),

inicio_do_par as (

    select source_system, warehouse_natural_key, product_natural_key, min(dia) as primeiro_movimento
    from movimentos_do_dia
    group by 1, 2, 3

),

fim_do_livro as (

    select source_system, max(dia) as ultimo_dia
    from movimentos_do_dia
    group by 1

),

abertura as (

    -- O que o par tinha ao abrir o trimestre: a soma de tudo antes dele, numa
    -- linha datada do primeiro dia do trimestre.
    select
        t.source_system,
        t.warehouse_natural_key,
        t.product_natural_key,
        t.year_number,
        t.quarter_number,
        l.primeiro_dia                              as dia,
        coalesce(sum(m.quantity_delta), 0)          as quantity_delta,
        coalesce(sum(m.inbound_quantity), 0)        as inbound_quantity,
        coalesce(sum(m.inbound_cost_amount), 0)     as inbound_cost_amount
    from trimestres t
    join limites l
      on  l.year_number = t.year_number
     and l.quarter_number = t.quarter_number
    left join movimentos_do_dia m
      on  m.source_system = t.source_system
     and m.warehouse_natural_key = t.warehouse_natural_key
     and m.product_natural_key = t.product_natural_key
     and m.dia < l.primeiro_dia
    group by 1, 2, 3, 4, 5, 6

),

dias as (

    select
        t.source_system,
        t.warehouse_natural_key,
        t.product_natural_key,
        t.year_number,
        t.quarter_number,
        d.full_date                                 as dia
    from trimestres t
    join {{ ref('dim_date') }} d
      on  d.year_number = t.year_number
     and d.quarter_number = t.quarter_number
    join inicio_do_par i
      on  i.source_system = t.source_system
     and i.warehouse_natural_key = t.warehouse_natural_key
     and i.product_natural_key = t.product_natural_key
    join fim_do_livro f
      on  f.source_system = t.source_system
    where d.full_date >= i.primeiro_movimento
      and d.full_date <= f.ultimo_dia

),

dias_e_movimentos as (

    -- Três fontes de linha por (par, trimestre, dia), somadas por dia: cada dia
    -- da grade, com delta zero; cada dia com movimento; e a abertura. É
    -- `union all` e não junção de propósito: juntar a grade de meio milhão de
    -- dias com os movimentos ou com a abertura levava o PostgreSQL a um laço
    -- aninhado de minutos. Só o dia da grade conta na média (`is_grid_day`).
    select
        source_system, warehouse_natural_key, product_natural_key, year_number, quarter_number, dia,
        1 as is_grid_day, 0 as quantity_delta, 0 as inbound_quantity, cast(0 as numeric) as inbound_cost_amount
    from dias
    union all
    select
        source_system, warehouse_natural_key, product_natural_key, year_number, quarter_number, dia,
        0, quantity_delta, inbound_quantity, inbound_cost_amount
    from movimentos_do_dia
    union all
    select
        source_system, warehouse_natural_key, product_natural_key, year_number, quarter_number, dia,
        0, quantity_delta, inbound_quantity, inbound_cost_amount
    from abertura

),

delta_do_dia as (

    select
        source_system, warehouse_natural_key, product_natural_key, year_number, quarter_number, dia,
        max(is_grid_day)                            as is_grid_day,
        sum(quantity_delta)                         as quantity_delta,
        sum(inbound_quantity)                       as inbound_quantity,
        sum(inbound_cost_amount)                    as inbound_cost_amount
    from dias_e_movimentos
    group by 1, 2, 3, 4, 5, 6

),

posicao_do_dia as (

    select
        source_system,
        warehouse_natural_key,
        product_natural_key,
        year_number,
        quarter_number,
        is_grid_day,
        sum(quantity_delta) over dentro_do_trimestre        as quantity_on_hand,
        sum(inbound_quantity) over dentro_do_trimestre      as inbound_quantity,
        sum(inbound_cost_amount) over dentro_do_trimestre   as inbound_cost_amount
    from delta_do_dia
    window dentro_do_trimestre as (
        partition by source_system, warehouse_natural_key, product_natural_key,
                     year_number, quarter_number
        order by dia
        rows between unbounded preceding and current row
    )

),

estoque_medio as (

    select
        source_system,
        warehouse_natural_key,
        product_natural_key,
        year_number,
        quarter_number,
        round(avg(cast(quantity_on_hand as numeric)), 2)    as avg_quantity_on_hand,
        -- Posição zero vale zero, com ou sem custo conhecido. O custo do dia é o
        -- médio ponderado das entradas até ele. O dia com posição e sem nenhuma
        -- entrada até ele não tem custo: a média do valor não se calcula sobre
        -- parte do trimestre e passaria por completa, então ela fica indefinida.
        case
            when {{ contar_onde('quantity_on_hand <> 0 and inbound_quantity = 0') }} > 0
            then null
            else round(avg(case
                when quantity_on_hand = 0 then cast(0 as numeric)
                else quantity_on_hand * inbound_cost_amount / nullif(inbound_quantity, 0)
            end), 2)
        end                                                 as avg_inventory_value_amount
    from posicao_do_dia
    -- Só os dias da grade: o trimestre sem venda, que só tem movimento, e o dia
    -- antes do primeiro movimento do par ficam de fora.
    where is_grid_day = 1
    group by 1, 2, 3, 4, 5

)

select
    s.year_number,
    s.quarter_number,
    s.year_number || '-T' || s.quarter_number       as year_quarter,
    s.sku,
    s.product_name,
    s.category_name,
    s.warehouse_name,
    s.warehouse_region,

    s.quantity_out,
    s.cost_of_goods_sold,
    coalesce(e.avg_quantity_on_hand, 0)             as avg_quantity_on_hand,
    e.avg_inventory_value_amount,
    case
        when e.avg_inventory_value_amount > 0
        then round(s.cost_of_goods_sold / e.avg_inventory_value_amount, 2)
    end                                             as inventory_turnover
from saidas s
left join estoque_medio e
    on  e.source_system = s.source_system
    and e.warehouse_natural_key = s.warehouse_natural_key
    and e.product_natural_key = s.product_natural_key
    and e.year_number = s.year_number
    and e.quarter_number = s.quarter_number
