-- V5 (Q67 e Q73 do plano da reabertura): a mediana trimestral do giro da P11 publicada dentro da faixa.
--
-- O giro mediano era 0,01 por trimestre: abertura e compra sorteadas sem relação com a venda. Desde a
-- V5 a compra e a abertura cobrem a venda dos 60 dias seguintes (`geracao.yml`), e a medida em memória
-- deu 0,47 no varejo e 0,50 no legado. A faixa é do Owner (`turnover_median_min` e `_max`, em
-- `dbt_project.yml`). A mediana é a das linhas com giro definido, as duas origens juntas, como a view
-- as publica. Falha por desenho no armazém da `v2.1.0` (0,02).

with mediana as (

    select {{ mediana('inventory_turnover') }} as giro_mediano
    from {{ ref('inventory_turnover_by_sku_and_warehouse') }}
    where inventory_turnover is not null

)

select giro_mediano
from mediana
where giro_mediano is null
   or giro_mediano < {{ var('turnover_median_min') }}
   or giro_mediano > {{ var('turnover_median_max') }}
