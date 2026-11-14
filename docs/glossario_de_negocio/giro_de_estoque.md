# Giro de estoque

{% docs inventory_turnover %}

**Giro de estoque** é quantas vezes o estoque de um SKU se renovou no período:
o custo do que saiu dividido pelo valor médio parado.

- **Cálculo:** `cost_of_goods_sold ÷ avg_inventory_value_amount`, por SKU,
  armazém e trimestre. O valor médio é a média, sobre os dias do trimestre, da
  posição de fim de dia do SKU no armazém, valorizada pelo custo médio ponderado
  das entradas até aquele dia (ADR-0052).
- **Os dias:** do início do trimestre, ou do primeiro movimento do SKU no
  armazém, até o fim do trimestre, ou o último dia registrado se ele não acabou.
  Pelo tempo do evento, no fuso de São Paulo.
- **Implementado em:** view `inventory_turnover_by_sku_and_warehouse`.
- **Relacionado:** custo do produto vendido, cobertura de estoque.

**O saldo é semiaditivo, e é aqui que isso importa.** `quantity_on_hand` soma
por armazém e por SKU, e **nunca ao longo do tempo**: somar o saldo de três
meses produz um estoque que nunca existiu — e produz um número plausível, que é
o pior tipo de erro. Por isso o saldo entra como média do período, não como
soma.

**Nada depois do trimestre entra.** Nem a quantidade nem o custo: uma compra
feita hoje não muda o giro de um trimestre fechado, pelo mesmo princípio do
custo do produto vendido.

**O que a média não vê.** O estoque que entra e sai no mesmo dia. No dado
sintético, toda saída sem lastro recebe uma correção de inventário um minuto
antes dela, e nesses SKUs a posição de fim de dia é zero: o giro fica
indefinido.

**Giro indefinido não é giro zero.** SKU sem estoque médio no período não girou
zero vezes: não havia o que girar. A view devolve nulo, e escrever zero ali
diria uma coisa diferente da que aconteceu.

{% enddocs %}
