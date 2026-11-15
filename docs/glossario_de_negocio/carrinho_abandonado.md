# Carrinho abandonado

{% docs abandoned_cart %}

**Carrinho abandonado** é o carrinho que teve ao menos um item adicionado e **não** virou pedido,
já tendo encerrado o seu ciclo — abandonado explicitamente ou expirado por prazo.

- **Cálculo:** carrinho com `cart_item_count > 0` e evento terminal em `abandoned` ou `expired`.
- **Implementado em:** `fact_cart_event`, evento terminal; medida `abandoned_cart_value`.
- **Relacionado:** taxa de conversão.

**Carrinho vazio não é carrinho abandonado**, e carrinho ainda dentro do prazo também não: o
primeiro nunca teve intenção de compra registrada, e o segundo ainda pode converter. Contar os dois
como abandono infla o funil e faz a taxa de conversão parecer pior do que é.

O **valor abandonado** é a soma de `quantity × unit_price` dos itens no momento em que entraram no
carrinho — preço praticado então, não o preço de hoje.

<!-- bigquery: fim do texto curto -->

<!-- gerado a partir dos modelos; não editar à mão -->
**Como as views o contam** (gerado de `docs/glossario_de_negocio/metricas.yml`; a definição e o porquê ficam no texto acima):

- `abandoned_cart_count`: soma de `f.abandoned_cart_count`, em `analytics.fact_cart_event`, pela criação do carrinho. Aditiva.
- `abandoned_value_amount`: soma de `f.abandoned_value_amount`, em `analytics.fact_cart_event`, pela criação do carrinho. Aditiva.
<!-- fim do trecho gerado -->

{% enddocs %}
