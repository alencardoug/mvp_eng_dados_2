# Lucro bruto

{% docs gross_profit %}

**Lucro bruto** é a receita líquida menos o custo do produto vendido. A
**margem bruta** é o lucro bruto dividido pela receita líquida.

- **Cálculo:** `net_revenue_amount − cost_of_goods_sold`, na granularidade
  comum às duas fatos que os fornecem.
- **Implementado em:** view `gross_margin_by_category`.
- **Relacionado:** receita líquida, custo do produto vendido.

**Frete e imposto ficam fora dos dois lados.** Não entram na receita líquida —
imposto é dedução e frete é valor de pedido, não de item — e não entram no
custo, que é o do produto. Lucro bruto é a margem do **produto**; frete e
tributo são resultado operacional, e pertencem a outra linha da demonstração.

**A margem é não aditiva.** Somar as margens de dois meses não dá a margem do
bimestre: some receita e custo, e divida de novo. A view entrega os três valores
lado a lado exatamente por isso.

**Receita e custo vêm de fatos diferentes**, com grãos diferentes, e são
combinados por *drill across* na granularidade comum — nunca por *join* linha a
linha. É o que torna a comparação legítima.

<!-- bigquery: fim do texto curto -->

<!-- gerado a partir dos modelos; não editar à mão -->
**Como as views o contam** (gerado de `docs/glossario_de_negocio/metricas.yml`; a definição e o porquê ficam no texto acima):

- `net_revenue_amount`: soma de `f.net_revenue_amount`, em `analytics.fact_sales_order_item`, pela data do pedido. Só pedido realizado — pago, em separação, enviado, entregue ou devolvido. Aditiva.
- `cost_of_goods_sold`: soma de `m.cogs_amount`, em `analytics.fact_inventory_movement`, pela data do movimento. Só a saída por venda expedida. Aditiva.
- `gross_profit_amount` = `net_revenue_amount` − `cost_of_goods_sold`. Aditiva.
- `gross_margin_pct` = 100 × `gross_profit_amount` ÷ `net_revenue_amount`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
<!-- fim do trecho gerado -->

{% enddocs %}
