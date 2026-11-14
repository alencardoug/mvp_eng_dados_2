# ADR-0052 — Calcular o giro pelo estoque médio do trimestre, a custo médio móvel

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 14/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | — (Q2 e Q8 do `PLANO_base_dos_consumidores.md`; F2 dos [Achados do nl_sql](../achados_nl_sql.md)) |
| Substitui / é substituída por | — |

## Contexto

A P11 pergunta o giro de estoque por SKU e armazém **no trimestre**, e o
[glossário](../glossario_de_negocio/giro_de_estoque.md) o define como o custo do que saiu dividido
pelo valor médio parado. A view `inventory_turnover_by_sku_and_warehouse` não media isso. O
denominador era o saldo **corrente** de `trusted.inventory_balances` multiplicado pela média do
custo unitário de **todos** os movimentos do par, inclusive os posteriores ao trimestre. O comentário
da view chamava isso de "aproximação declarada", e o efeito era o que o
[ADR-0030](0030-cmv-do-livro-de-estoque.md) recusou para a margem: uma compra feita hoje mudava o giro
de 2024. O `nl_sql` retirou a pergunta do teste por isso (F2).

A Q2 do plano decidiu medir pelo estoque médio do período. A Q8 decidiu como, sobre o diagnóstico de
14/11/2026 no armazém local. Os números estão em
`data/medicoes/base_consumidores/bloco1/f2_diagnostico_e_proposta.md`, fora do Git:

- nenhum evento atrasado cruza trimestre (atraso máximo de 900 s), então o tempo de evento é seguro;
- o custo unitário varia pouco dentro do par (amplitude média de 2,0% no retail e 0,9% no legado);
- 16 pares ficam negativos em algum instante, 2 pares do legado divergem da projeção por movimentos
  na quarentena, e 166 pares não começam pelo estoque de abertura;
- o gerador cria uma **correção-relâmpago**: quando uma saída não tem lastro, entra um
  `adjustment_in` um minuto antes dela (`generator/domains/estoque.py`). São 1.514 ajustes, cerca de
  um terço dos ajustes de entrada. Nesses pares a posição de fim de dia é zero mesmo com venda.

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **Média diária da posição de fim de dia, a custo médio móvel** | Fiel ao que ficou parado em cada dia e simples de auditar: uma linha por dia, por par. Não usa nada posterior ao dia | Não enxerga o estoque que entra e sai no mesmo dia. Nos pares da correção-relâmpago, o giro fica indefinido |
| Média ponderada pelo tempo entre eventos | Conta cada minuto de estoque | O estoque de um minuto da correção-relâmpago dá denominadores ínfimos e giros enormes, um número plausível e falso |
| (Abertura + fechamento) ÷ 2 | A convenção contábil curta, a mais barata de calcular | Cega ao que acontece dentro do trimestre: um par que esvazia e reabastece no meio dele parece parado |
| Valorizar pelo custo do último movimento | Mais simples que a média móvel | Um movimento isolado, bom ou ruim, revaloriza o estoque do dia inteiro |
| Valorizar pela média do custo do próprio trimestre | Não usa custo futuro | O trimestre sem movimento fica sem custo, com o estoque parado ali |
| Manter os nomes `quantity_on_hand` e `inventory_value_amount` | Esquema igual, nenhum aviso de mudança | O nome continua dizendo saldo corrente, e o valor passa a ser média |
| Giro nulo no par-trimestre com posição negativa ou deriva | Não publica número de histórico quebrado | Esconde trimestres inteiros por um instante negativo, e o livro é a fonte da verdade (Modelo de Dados §2.10) |
| Corrigir o gerador antes | O dado ficaria realista | Regenerar as duas origens é destrutivo e refaz todos os números já conferidos, fora desta fase |

## Decisão

**O giro do trimestre é o CMV do trimestre dividido pelo valor médio do estoque nele: a média,
sobre os dias do trimestre, da posição de fim de dia do par, valorizada pelo custo médio ponderado
das entradas até aquele dia.**

- **Fonte:** o livro, `fact_inventory_movement`, pelo par natural (origem, armazém, SKU). A
  projeção de `trusted` deixa de ser lida.
- **Tempo:** o de evento (`occurred_at`), no fuso de São Paulo, pela `dim_date`. Os dias contam do
  primeiro dia do trimestre, ou do dia do primeiro movimento do par se ele vier depois, até o fim do
  trimestre ou o último dia do livro, se o trimestre ainda não acabou.
- **Valor do dia:** posição × (custo acumulado das entradas ÷ quantidade acumulada das entradas),
  ambos até o fim do dia. Nada posterior ao dia entra.
- **Esquema:** as colunas passam a `avg_quantity_on_hand` e `avg_inventory_value_amount`. O giro
  continua indefinido (nulo) quando o valor médio é zero ou negativo.
- **Histórico incompleto:** calcula-se com o livro como ele está. A posição negativa entra na média,
  e a limitação fica escrita na descrição da view e no glossário.
- **A correção-relâmpago do gerador** fica registrada como trabalho adiado
  ([V4 das Pendências](../pendencias.md#v4--a-correção-relâmpago-do-gerador-de-estoque-registrada-em-14112026)).

## Consequências

- **Positivas:** o giro de um trimestre fechado deixa de mudar com movimento posterior, pelo mesmo
  princípio do ADR-0030. A view lê só `analytics`, como as outras, e o nome das colunas diz o que
  elas são.
- **Negativas:** a view fica mais cara: uma grade de dias por par, com janela acumulada. O estoque
  intradiário não aparece, e nos pares da correção-relâmpago o giro fica indefinido onde antes
  aparecia (ou aparecia errado). Hoje são 1.216 linhas indefinidas de 6.990, contra 620. A mudança de
  esquema obriga o aviso prévio ao BI ([Consumidores §5](../consumidores.md#5-o-que-mudou-para-quem-consome)).
- **Paridade com o GCP:** a mesma consulta no BigQuery, com `GENERATE_DATE_ARRAY` (ou a `dim_date`)
  para a grade de dias e `SUM() OVER (PARTITION BY … ORDER BY …)` para o acumulado. Nada de
  específico do PostgreSQL. As macros portáveis do projeto cobrem o fuso.
- **Documentos a atualizar:** o [glossário do giro](../glossario_de_negocio/giro_de_estoque.md); a
  descrição da view em `dbt/models/consumption/_consumption__models.yml`; as
  [Pendências](../pendencias.md) (V4); os [Consumidores](../consumidores.md) §5.
