-- O par SKU × armazém e o seu ponto de reposição (ADR-0057; Q75 do plano do ponto de reposição).
--
-- ═══ Por que uma dimensão ═════════════════════════════════════════════════════
-- É a entidade que o varejo chama de item-local: o lugar onde um ERP guarda o
-- ponto de reposição de cada SKU em cada armazém. A origem não tem esse ponto,
-- então ele é **derivado da demanda** do próprio par, pela regra do ADR-0057:
--
--   ponto = teto( venda dos últimos N dias ÷ N × (prazo de reposição + margem) )
--
-- Tipo 1: o valor de hoje, sem histórico. Muda a cada *build*, porque a venda
-- muda; quem precisa do ponto de um instante passado lê a fotografia guardada
-- com a execução do *streaming*, não esta tabela.
--
-- ── A identidade é natural, e não a versão do produto ───────────────────────
-- A fato liga cada movimento à versão do produto vigente nele (ADR-0017). Aqui
-- a venda é somada através de **todas** as versões, resolvidas para a chave
-- natural antes de agregar, e a chave substituta é o *hash* da identidade
-- natural: estável quando o produto ganha versão nova. As FKs são resolvidas
-- **depois** de agregar: o armazém (tipo 1) e a versão **corrente** do produto.
-- Par sem versão corrente fica fora, como fica fora da P12, que junta pela
-- corrente.
--
-- ── O instante é o do lote, e não `current_date` ────────────────────────────
-- A janela termina no último movimento da fato (o lado frio). A P12 mede o
-- saldo pelo livro inteiro, frio e quente; o ponto, só pelo frio, e por isso
-- ele anda a cada *build*, não a cada evento (ADR-0057, Consequências).

with agora as (

    select max(occurred_at) as instante
    from {{ ref('fact_inventory_movement') }}

),

{#- A venda dentro da janela própria do ponto: a cobertura da P12 usa outra,
    de 90 dias, e a ruptura censuraria a venda numa janela curta (ADR-0057). -#}
{% set venda_na_janela -%}
m.is_sale
          and m.occurred_at >= {{ dias_no_calendario('(select instante from agora)', -var("reorder_demand_window_days")) }}
{%- endset %}

movimento as (

    select
        f.source_system,
        w.warehouse_natural_key,
        p.product_natural_key,
        f.is_sale,
        f.quantity_out,
        f.occurred_at
    from {{ ref('fact_inventory_movement') }} f
    join {{ ref('dim_warehouse') }} w on w.warehouse_key = f.warehouse_key
    join {{ ref('dim_product') }} p   on p.product_key = f.product_key

),

par as (

    select
        m.source_system,
        m.warehouse_natural_key,
        m.product_natural_key,
        coalesce({{ agregado_onde('sum', 'm.quantity_out', venda_na_janela) }}, 0) as window_sold_units
    from movimento m
    group by m.source_system, m.warehouse_natural_key, m.product_natural_key

)

select
    {{ dbt_utils.generate_surrogate_key(['par.source_system', 'par.warehouse_natural_key', 'par.product_natural_key']) }}
                                                            as sku_location_key,
    par.source_system,
    w.warehouse_key,
    p.product_key,
    par.warehouse_natural_key,
    par.product_natural_key,

    -- ── A demanda ───────────────────────────────────────────────────────────
    (select instante from agora)                            as demand_window_end_at,
    cast({{ var("reorder_demand_window_days") }} as integer) as demand_window_days,
    cast(par.window_sold_units as integer)                  as window_sold_units,

    -- ── A regra ─────────────────────────────────────────────────────────────
    cast({{ var("reorder_lead_time_days") }} as integer)    as lead_time_days,
    cast({{ var("reorder_safety_days") }} as integer)       as safety_days,
    -- Inteiro desde a origem: a venda e os dias são inteiros, e o teto da razão
    -- é feito em `numeric`, sem `float` no caminho.
    cast(
        ceil(
            cast(par.window_sold_units * ({{ var("reorder_lead_time_days") }} + {{ var("reorder_safety_days") }}) as numeric)
            / {{ var("reorder_demand_window_days") }}
        ) as integer
    )                                                       as reorder_point
from par
join {{ ref('dim_warehouse') }} w
  on  w.source_system = par.source_system
 and w.warehouse_natural_key = par.warehouse_natural_key
join {{ ref('dim_product') }} p
  on  p.source_system = par.source_system
 and p.product_natural_key = par.product_natural_key
 and p.is_current
