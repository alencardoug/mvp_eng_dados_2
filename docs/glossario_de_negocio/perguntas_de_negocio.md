# Perguntas de Negócio

> **O que vive aqui:** as perguntas que o datamart existe para responder, e o que cada uma exige do
> modelo dimensional — fato, medidas com a sua aditividade, dimensões e a view de consumo.
>
> **O que não vive aqui:** a definição dos conceitos que as perguntas usam (ver os arquivos de
> conceito neste mesmo diretório); o grão e a contagem de cada fato (ver
> [Modelo de Dados](../modelo_de_dados.md#3-modelo-dimensional--26-tabelas-em-analytics)); a
> materialização das views (ver [ADR-0016](../adr/0016-materializacao-por-camada.md)).

| Campo | Informação |
|---|---|
| Método | Perguntas antes do SQL ([ADR-0018](../adr/0018-fatos-e-views-a-partir-de-perguntas-de-negocio.md)) |
| Quantidade | 16 |
| Situação | **As 16 com view construída**, todas com `contract: enforced` |
| Última revisão | 19/10/2026 |

---

## 1. Como ler esta lista

Uma pergunta é concreta quando nomeia a **métrica**, o **recorte** e o **período**. *"Qual a margem
por categoria e canal no trimestre?"* é pergunta; *"analisar vendas"* não é.

Cada pergunta declara o que exige do modelo:

- as **medidas**, classificadas como **aditiva** (soma em qualquer dimensão), **semiaditiva** (soma
  em todas menos tempo — o caso do saldo de estoque) ou **não aditiva** (razões e percentuais, que
  se recalculam a cada recorte e nunca se somam);
- as **dimensões conformadas** que a atendem;
- a **view de consumo** que a responde, com `contract: enforced`.

**A aditividade não é anotação: é o que impede erro.** Somar uma medida semiaditiva ao longo do
tempo produz um número que parece certo e não é — saldo de estoque somado mês a mês vira uma
quantidade que nunca existiu. Declará-la aqui é o que permite ao teste detectar o erro em vez de
apenas documentá-lo.

As views não recebem prefixo de tipo: são nomeadas pela pergunta que respondem
([ADR-0013](../adr/0013-nomenclatura-por-prefixo-de-tipo.md)). O nome é em inglês, como todo objeto
de banco; a pergunta é em português, como todo documento.

---

## 2. Núcleo comercial — Etapa 5

Estas sete são as que viram view agora. Cinco se apoiam em `fact_sales_order_item`, cujo grão é
**uma linha de item de pedido**; a P04, em `fact_order_status_event`, no grão do pedido (F18); a P07,
em `fact_cart_event`.

O ADR-0018 previa "12 a 15 perguntas". São 16 porque a decisão de acrescentar a fato de carrinho —
tomada ao redigir esta lista, e registrada no
[ADR-0028](../adr/0028-fato-de-carrinho-para-o-funil.md) — trouxe junto a pergunta que a justifica.

### P01 — Qual a receita líquida por mês, canal e categoria de produto?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_sales_order_item` |
| **Medidas** | `order_count` (**não aditiva** — entre categorias: um pedido com itens de duas categorias conta nas duas) · `unit_count` (aditiva) · `gross_revenue_amount` (aditiva) · `discount_amount` (aditiva) · `net_revenue_amount` (aditiva) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_category` |
| **View** | `monthly_revenue_by_channel_and_category` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_sales_order_item`, pela data do pedido. Só pedido realizado — pago, em separação, enviado, entregue ou devolvido.
- `order_count`: contagem distinta de (`f.source_system`, `f.order_id`).
- `unit_count`: soma de `f.quantity`.
- `gross_revenue_amount`: soma de `f.gross_revenue_amount`.
- `discount_amount`: soma de `f.discount_amount`.
- `net_revenue_amount`: soma de `f.net_revenue_amount`.
<!-- fim do trecho gerado -->

É a pergunta base do datamart: todas as outras a recortam de outra forma. É também a que fixa a
definição de [receita líquida](receita_liquida.md), da qual dependem P02, P03, P05 e P06.

### P02 — Qual o ticket médio por pedido, por canal e por segmento de cliente, mês a mês?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_sales_order_item` |
| **Medidas** | `order_count` (aditiva — contagem distinta de pedido) · `net_revenue_amount` (aditiva) · `average_order_value` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_customer` |
| **View** | `average_order_value_by_channel_and_segment` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_sales_order_item`, pela data do pedido. Só pedido realizado — pago, em separação, enviado, entregue ou devolvido.
- `order_count`: contagem distinta de (`f.source_system`, `f.order_id`).
- `net_revenue_amount`: soma de `f.net_revenue_amount`.
- `average_order_value` = `net_revenue_amount` ÷ `order_count`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
<!-- fim do trecho gerado -->

O [ticket médio](ticket_medio.md) é razão, não soma: a média das médias mensais não é a média do
ano. A view entrega numerador e denominador ao lado do resultado, para que qualquer reagregação
seja possível sem recalcular errado.

### P03 — Quais os 25 SKUs de maior receita no período, e quanto cada um pesa na receita da sua categoria?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_sales_order_item` |
| **Medidas** | `revenue_rank` (**não aditiva**) · `unit_count` (aditiva) · `net_revenue_amount` (aditiva) · `category_net_revenue_amount` (**não aditiva**) · `category_revenue_share_pct` (**não aditiva**) |
| **Dimensões** | `dim_product` · `dim_category` · `dim_brand` |
| **View** | `top_skus_by_revenue` |

**Conferida por referência** (gerado de `docs/glossario_de_negocio/metricas.yml`): `tests/test_auditoria_das_views.py::test_a_view_confere_com_a_referencia`, contra `tests/auditoria/top_skus_by_revenue.sql`. O ranking e o corte — `rank()` sobre a receita dentro da categoria, e a participação na receita da categoria — não cabem no montador.
<!-- fim do trecho gerado -->

### P04 — Quantos clientes compraram pela primeira vez em cada mês, e quantos deles voltaram a comprar em 90 dias?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_order_status_event` — a estreia e a recompra, pelo evento de criação do pedido realizado; inclusive o pedido de itens rejeitados em cascata (F18) |
| **Medidas** | `new_customer_count` (aditiva) · `returning_customer_count` (aditiva) · `repeat_purchase_rate_pct` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_customer` |
| **View** | `new_and_repeat_customers_by_month` |

**Conferida por referência** (gerado de `docs/glossario_de_negocio/metricas.yml`): `tests/test_auditoria_das_views.py::test_a_view_confere_com_a_referencia`, contra `tests/auditoria/new_and_repeat_customers_by_month.sql`. A estreia e a recompra saem de uma janela sobre a ordem dos pedidos realizados de cada cliente (F18), que o montador não faz.
<!-- fim do trecho gerado -->

Depende dos conceitos de [cliente ativo](cliente_ativo.md) e
[recorrência de compra](recorrencia_de_compra.md). É a pergunta que a Etapa 9 estende para *churn*.

### P05 — Qual a receita e o número de pedidos por estado e região de entrega, por trimestre?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_sales_order_item` |
| **Medidas** | `order_count` (aditiva — contagem distinta de pedido) · `customer_version_count` (**não aditiva**) · `unit_count` (aditiva) · `net_revenue_amount` (aditiva) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_geography` |
| **View** | `revenue_by_delivery_region` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_sales_order_item`, pela data do pedido. Só pedido realizado — pago, em separação, enviado, entregue ou devolvido.
- `order_count`: contagem distinta de (`f.source_system`, `f.order_id`).
- `customer_version_count`: contagem distinta de `f.customer_key`.
- `unit_count`: soma de `f.quantity`.
- `net_revenue_amount`: soma de `f.net_revenue_amount`.
<!-- fim do trecho gerado -->

`dim_geography` é conformada: a mesma dimensão atende entrega aqui e origem de remessa na Etapa 8.

### P06 — Qual o desconto concedido como fração da receita bruta, por canal e mês?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_sales_order_item` |
| **Medidas** | `order_count` (**não aditiva** — entre categorias: um pedido com itens de duas categorias conta nas duas) · `gross_revenue_amount` (aditiva) · `discount_amount` (aditiva) · `net_revenue_amount` (aditiva) · `discount_share_pct` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_category` |
| **View** | `discount_share_by_channel` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_sales_order_item`, pela data do pedido. Só pedido realizado — pago, em separação, enviado, entregue ou devolvido.
- `order_count`: contagem distinta de (`f.source_system`, `f.order_id`).
- `gross_revenue_amount`: soma de `f.gross_revenue_amount`.
- `discount_amount`: soma de `f.discount_amount`.
- `net_revenue_amount`: soma de `f.net_revenue_amount`.
- `discount_share_pct` = 100 × `discount_amount` ÷ `gross_revenue_amount`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
<!-- fim do trecho gerado -->

Na Etapa 9, com `fact_coupon_redemption` construída, esta pergunta ganha o recorte por campanha —
mas a view atual permanece: mudança quebrante nasce como `v2`
([ADR-0018](../adr/0018-fatos-e-views-a-partir-de-perguntas-de-negocio.md)).

### P07 — Qual a taxa de conversão de carrinho em pedido, por canal e mês?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_cart_event` |
| **Medidas** | `cart_count` (aditiva) · `closed_cart_count` (aditiva) · `converted_cart_count` (aditiva) · `abandoned_cart_count` (aditiva) · `cart_conversion_rate_pct` (**não aditiva**) · `cart_value_amount` (aditiva) · `abandoned_value_amount` (aditiva) |
| **Dimensões** | `dim_date` · `dim_sales_channel` |
| **View** | `cart_conversion_rate_by_channel` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_cart_event`, pela criação do carrinho. Sem filtro.
- `cart_count`: soma de `f.cart_count`.
- `closed_cart_count`: soma de `f.closed_cart_count`.
- `converted_cart_count`: soma de `f.converted_cart_count`.
- `abandoned_cart_count`: soma de `f.abandoned_cart_count`.
- `cart_conversion_rate_pct` = 100 × `converted_cart_count` ÷ `closed_cart_count`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
- `cart_value_amount`: soma de `f.cart_value_amount`.
- `abandoned_value_amount`: soma de `f.abandoned_value_amount`.
<!-- fim do trecho gerado -->

Usa [carrinho abandonado](carrinho_abandonado.md) e [taxa de conversão](taxa_de_conversao.md). É a
pergunta que justifica a décima fato ([ADR-0028](../adr/0028-fato-de-carrinho-para-o-funil.md)):
sem ela, `carts` e `cart_items` — 1,5 dos 2,5 milhões de linhas da proporção de referência — seriam
gerados, ingeridos e limpos para não alimentar pergunta nenhuma.

---

## 3. Financeiro e estoque — Etapa 6

Estas quatro viraram view na Etapa 6. A **P08** é a primeira que combina duas
fatos: receita vem de `fact_sales_order_item` e custo de `fact_inventory_movement`,
cada uma agregada ao seu grão e depois cruzadas na granularidade comum
([ADR-0030](../adr/0030-cmv-do-livro-de-estoque.md)).

### P08 — Qual o lucro bruto e a margem por categoria e mês?

Usa [lucro bruto](lucro_bruto.md) e
[custo do produto vendido](custo_do_produto_vendido.md).

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fatos** | `fact_sales_order_item` · `fact_inventory_movement` |
| **Medidas** | `net_revenue_amount` (aditiva) · `cost_of_goods_sold` (aditiva) · `gross_profit_amount` (aditiva) · `gross_margin_pct` (**não aditiva**) · `unit_count` (aditiva) · `dispatched_unit_count` (aditiva) |
| **Dimensões** | `dim_date` · `dim_category` · `dim_product` |
| **View** | `gross_margin_by_category` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_sales_order_item`, pela data do pedido. Só pedido realizado — pago, em separação, enviado, entregue ou devolvido.
- `analytics.fact_inventory_movement`, pela data do movimento. Só a saída por venda expedida. Liga `analytics.dim_category` por `cat.source_system = p.source_system` e `cat.category_natural_key = p.product_category_id`.
- As duas fontes se combinam por `year_month` e `category_name`: a linha de um lado só aparece, com `0` no lado ausente.
- `net_revenue_amount`: soma de `f.net_revenue_amount`.
- `cost_of_goods_sold`: soma de `m.cogs_amount`.
- `gross_profit_amount` = `net_revenue_amount` − `cost_of_goods_sold`. Aditiva.
- `gross_margin_pct` = 100 × `gross_profit_amount` ÷ `net_revenue_amount`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
- `unit_count`: soma de `f.quantity`.
- `dispatched_unit_count`: soma de `m.quantity_out`.
<!-- fim do trecho gerado -->

### P09 — Qual a taxa de aprovação de pagamento por meio de pagamento e número de parcelas?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_payment_transaction` |
| **Medidas** | `authorization_attempt_count` (aditiva) · `approved_authorization_count` (aditiva) · `approval_rate_pct` (**não aditiva**) · `authorized_amount` (aditiva) · `captured_amount` (aditiva) |
| **Dimensões** | `dim_date` · `dim_payment_method` |
| **View** | `payment_approval_rate_by_method` |

**Conferida por referência** (gerado de `docs/glossario_de_negocio/metricas.yml`): `tests/test_auditoria_das_views.py::test_a_view_confere_com_a_referencia`, contra `tests/auditoria/payment_approval_rate_by_method.sql`. O capturado é atribuído à primeira autorização aprovada do pagamento (D67), por uma janela; as tentativas e a aprovação vêm da mesma leitura.
<!-- fim do trecho gerado -->

**Como se conta.** O denominador é a **tentativa de autorização**, não o pagamento: cada transação
de autorização é uma tentativa, e o numerador são as aprovadas. É o atrito que se quer ver — um
pagamento aprovado na terceira tentativa contribui com uma aprovação e três tentativas. O mês é o da
tentativa. O valor capturado de cada pagamento vai para o grupo (meio e parcelamento) da sua
**primeira** autorização aprovada, e só para ele, para que o capturado da view seja todo o capturado
da fato, nem mais nem menos (D67).

### P10 — Qual o valor reembolsado como fração do capturado, por motivo e mês?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fatos** | `fact_refund` · `fact_payment_transaction` |
| **Medidas** | `refund_count` (aditiva) · `refunded_amount` (aditiva) · `captured_amount` (**não aditiva** — o capturado do mês e do meio se repete em cada motivo) · `refund_rate_pct` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_payment_method` |
| **View** | `refund_rate_by_reason` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_refund`, pela data do reembolso. Sem filtro.
- `analytics.fact_payment_transaction`, pela data da transação. Sem filtro. Agregada só por `year_month`, `payment_method_name`: o valor se repete em cada linha do grão da view que casa com ela.
- As duas fontes se combinam por `year_month` e `payment_method_name`: toda linha da primeira fica; sem par, a segunda fica com `0`.
- `refund_count`: soma de `f.refund_count`.
- `refunded_amount`: soma de `f.completed_refund_amount`.
- `captured_amount`: soma de `t.captured_amount`.
- `refund_rate_pct` = 100 × `refunded_amount` ÷ `captured_amount`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
<!-- fim do trecho gerado -->

**Por que se conta assim.** A pergunta é quanto do que entrou no mês saiu de volta. Por isso o
denominador é **todo o capturado do mês** naquele meio de pagamento, e não o capturado da transação
reembolsada; e por isso ele se repete em cada linha de motivo do mesmo mês e meio, e não se soma entre
motivos. Na fato, o valor é só o dos reembolsos **concluídos** (`completed_refund_amount`), e a contagem
inclui também os solicitados e os recusados.

### P11 — Qual o giro de estoque por SKU e armazém no trimestre?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_inventory_movement` |
| **Medidas** | `quantity_out` (aditiva) · `cost_of_goods_sold` (aditiva) · `avg_quantity_on_hand` (**semiaditiva** — soma por armazém e SKU, nunca ao longo do tempo) · `avg_inventory_value_amount` (**semiaditiva** — soma por armazém e SKU, nunca ao longo do tempo) · `inventory_turnover` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_product` · `dim_category` · `dim_warehouse` |
| **View** | `inventory_turnover_by_sku_and_warehouse` |

**Conferida por referência** (gerado de `docs/glossario_de_negocio/metricas.yml`): `tests/test_auditoria_das_views.py::test_a_view_confere_com_a_referencia`, contra `tests/auditoria/inventory_turnover_by_sku_and_warehouse.sql`. O giro é pelo estoque médio do trimestre (ADR-0052), reconstruído dia a dia a partir do livro; o montador agrega, não reconstrói saldo.
<!-- fim do trecho gerado -->

É a pergunta que exige a aditividade declarada: somar `quantity_on_hand` de três meses produz um
estoque que nunca existiu.

---

## 4. Estoque em tempo real — Etapa 7

### P12 — Quais SKUs estão abaixo do ponto de reposição agora, por armazém?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_inventory_movement` — e os deltas que ela ainda não absorveu, pelo saldo de `trusted.inventory_balances` |
| **Medidas** | `quantity_on_hand` (**semiaditiva**) · `quantity_reserved` (**semiaditiva**) · `quantity_available` (**semiaditiva**) · `quantity_from_batch` (**semiaditiva**) · `quantity_from_stream` (**semiaditiva**) · `stream_movement_count` (aditiva) · `reorder_point` (**não aditiva**) · `is_stockout` (**não aditiva**) · `daily_demand_units` (**não aditiva**) · `days_of_cover` (**não aditiva**) · `last_movement_at` (**não aditiva**) |
| **Dimensões** | `dim_product` · `dim_warehouse` |
| **View** | `skus_below_reorder_point` |

**Conferida por referência** (gerado de `docs/glossario_de_negocio/metricas.yml`): `tests/test_auditoria_das_views.py::test_a_view_confere_com_a_referencia`, contra `tests/auditoria/skus_below_reorder_point.sql`. O saldo de agora é o do lote mais os deltas do caminho quente, e a demanda diária e a cobertura saem de janelas sobre o livro; nada disso é agregado de uma fonte.
<!-- fim do trecho gerado -->

Depende de [ruptura de estoque](ruptura_de_estoque.md) e de
[cobertura de estoque](cobertura_de_estoque.md) — os dois conceitos escritos na Etapa 7, que é a
que construiu o modelo correspondente.

É a única pergunta cuja resposta muda entre duas execuções seguidas sem ninguém rodar nada, e por
isso a única que exercita o caminho quente. A composição está descrita em
[Streaming §4.1](../streaming.md#41-onde-o-quente-e-o-frio-se-encontram): a fronteira entre o que a
fato já absorveu e o que só existe no fluxo é a **ausência do `movement_id` na fato**, e não um
corte por tempo — que perderia justamente o evento atrasado.

---

## 5. Entrega e logística — Etapa 8

Estas duas viraram view na Etapa 8, e são o par que mais exige atenção da lista: **medem coisas
diferentes e não se cruzam**. P13 conta **remessas** — é nelas que vivem transportadora, modalidade
e a promessa de prazo — e P14 conta **pedidos**, fechando na última remessa a chegar. Um pedido
dividido em duas caixas aparece duas vezes lá e uma vez aqui; um pedido com uma caixa entregue e
outra extraviada aparece lá e **não** aparece aqui.

A separação é decisão registrada ([ADR-0033](../adr/0033-entrega-medida-em-dois-graos.md)), e os
dois conceitos correspondentes — [entrega no prazo](entrega_no_prazo.md) e
[ciclo de entrega](ciclo_de_entrega.md) — dizem cada um, na própria definição, que o outro existe e
em que grão vive. A data de chegada das duas vem do livro `delivery_events`, não da coluna da
remessa ([ADR-0034](../adr/0034-entrega-do-livro-de-eventos.md)).

### P13 — Qual a fração de entregas dentro do prazo prometido, por transportadora e modalidade, mês a mês?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_shipment` — toda remessa entregue, inclusive a de itens rejeitados em cascata ([ADR-0053](../adr/0053-fato-no-grao-da-remessa.md)) |
| **Medidas** | `delivered_count` (aditiva) · `on_time_count` (aditiva) · `late_count` (aditiva) · `split_order_shipment_count` (aditiva) · `on_time_rate` (**não aditiva**) · `avg_delay_days_when_late` (**não aditiva**) · `avg_transit_days` (**não aditiva**) · `failed_attempt_count` (aditiva) |
| **Dimensões** | `dim_date` · `dim_carrier` · `dim_warehouse` |
| **View** | `on_time_delivery_rate_by_carrier` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_shipment`, pela data da entrega. Só a remessa entregue (ADR-0053, D66).
- `delivered_count`: contagem das linhas.
- `on_time_count`: contagem das linhas com `f.is_on_time`.
- `late_count`: contagem das linhas com `not f.is_on_time`.
- `split_order_shipment_count`: contagem das linhas com `f.is_split_order`.
- `on_time_rate` = `on_time_count` ÷ `delivered_count`, arredondada a 4 casas; nula com o denominador zero. Não aditiva.
- `avg_delay_days_when_late`: média de `f.delivery_delay_days`, só onde `not f.is_on_time`, arredondada a 4 casas.
- `avg_transit_days`: média de `f.transit_days`, arredondada a 4 casas.
- `failed_attempt_count`: soma de `f.failed_attempt_count`.
<!-- fim do trecho gerado -->

### P14 — Qual o tempo médio entre pedido e entrega, por região e modalidade?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fato** | `fact_shipment` — a remessa que fecha o ciclo do pedido; inclusive o pedido de itens rejeitados em cascata (F17) |
| **Medidas** | `order_count` (aditiva) · `split_order_count` (aditiva) · `shipment_count` (aditiva) · `avg_order_to_delivery_days` (**não aditiva**) · `median_order_to_delivery_days` (**não aditiva**) · `max_order_to_delivery_days` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_carrier` · `dim_geography` |
| **View** | `order_to_delivery_time_by_region` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_shipment`, pela data da entrega. Só o pedido de ciclo fechado, na remessa que fechou o ciclo.
- `order_count`: contagem das linhas.
- `split_order_count`: contagem das linhas com `f.is_split_order`.
- `shipment_count`: soma de `f.order_shipment_count`.
- `avg_order_to_delivery_days`: média de `f.order_to_delivery_days`, arredondada a 4 casas.
- `median_order_to_delivery_days`: mediana de `f.order_to_delivery_days`, arredondada a 4 casas.
- `max_order_to_delivery_days`: máximo de `f.order_to_delivery_days`, arredondada a 4 casas.
<!-- fim do trecho gerado -->

---

## 6. Relacionamento e atendimento — Etapa 9

As duas últimas, e as duas que combinam a fato de atendimento com a de vendas por *drill across* —
nenhuma das duas está no grão da resposta, e cada uma é reduzida ao seu antes de se encontrarem.

**P15 tem denominador de canal, não de categoria.** Pedido não tem categoria de chamado, e a coluna
se chama `channel_order_count` para dizer isso: ela se repete em cada linha de categoria.

**P16 mudou de âncora.** Os 90 dias correm do **pedido**, não da estreia do cliente
([ADR-0036](../adr/0036-recompra-ancorada-no-pedido.md)), porque é o que dá aos dois grupos
comparados a mesma janela. O conceito correspondente é
[recompra pós-pedido](recompra_pos_pedido.md), que **não** é a recompra de P04: aquela conta
clientes de uma coorte de estreia, esta conta pedidos.

### P15 — Quantos chamados por 100 pedidos, por categoria de chamado e canal, mês a mês?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fatos** | `fact_support_ticket_event` · `fact_order_status_event` — o denominador vem de `fact_order_status_event`, pelo grão do pedido (F21) |
| **Medidas** | `ticket_count` (aditiva) · `high_priority_ticket_count` (aditiva) · `reopened_ticket_count` (aditiva) · `solved_first_time_count` (aditiva) · `channel_order_count` (**não aditiva**) · `tickets_per_hundred_orders` (**não aditiva**) · `avg_hours_to_resolution` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_support_category` |
| **View** | `support_tickets_per_hundred_orders` |

**Como se monta** (gerado de `docs/glossario_de_negocio/metricas.yml`):

- `analytics.fact_support_ticket_event`, pela abertura do chamado. Um chamado é contado uma vez, pelo evento de abertura.
- `analytics.fact_order_status_event`, pela criação do pedido. O pedido realizado, pelo evento de criação; inclusive o de itens rejeitados em cascata (F21). Agregada só por `year_month`, `sales_channel_name`: o valor se repete em cada linha do grão da view que casa com ela.
- As duas fontes se combinam por `year_month` e `sales_channel_name`: toda linha da primeira fica; sem par, a segunda fica com nulo.
- `ticket_count`: contagem das linhas.
- `high_priority_ticket_count`: contagem das linhas com `f.ticket_priority in ('high', 'urgent')`.
- `reopened_ticket_count`: contagem das linhas com `f.was_reopened`.
- `solved_first_time_count`: contagem das linhas com `f.is_solved_first_time`.
- `channel_order_count`: contagem distinta de (`f.source_system`, `f.order_id`).
- `tickets_per_hundred_orders` = 100 × `ticket_count` ÷ `channel_order_count`, arredondada a 4 casas; nula com o denominador zero. Não aditiva.
- `avg_hours_to_resolution`: média de `f.hours_to_resolution`, arredondada a 2 casas.
<!-- fim do trecho gerado -->

**Por que se conta assim.** O canal e a categoria entram pelo **nome**, e o denominador soma todas as
origens do canal, tenham elas chamado ou não (F1 dos Achados do `nl_sql`). O chamado sem pedido fica no
canal "Sem canal", sem denominador, e a taxa é nula ali.

### P16 — Qual a taxa de recompra em 90 dias dos clientes que abriram chamado, comparada à dos que não abriram?

<!-- gerado a partir dos modelos; não editar à mão -->
| | |
|---|---|
| **Fatos** | `fact_sales_order_item` · `fact_support_ticket_event` |
| **Medidas** | `order_count` (aditiva) · `repeat_order_count` (**não aditiva**) · `repeat_purchase_rate` (**não aditiva**) · `avg_days_to_next_order` (**não aditiva**) |
| **Dimensões** | `dim_date` · `dim_sales_channel` · `dim_support_category` |
| **View** | `repeat_purchase_rate_after_support` |

**Conferida por referência** (gerado de `docs/glossario_de_negocio/metricas.yml`): `tests/test_auditoria_das_views.py::test_a_view_confere_com_a_referencia`, contra `tests/auditoria/repeat_purchase_rate_after_support.sql`. O pedido seguinte de cada cliente, dentro da janela, sai de uma janela sobre os pedidos realizados; o montador não ordena pedidos.
<!-- fim do trecho gerado -->

A unidade é o **pedido**, não o cliente: é o que permite comparar quem abriu chamado com quem não
abriu sob a mesma âncora. Depende de [recompra pós-pedido](recompra_pos_pedido.md) e de
[churn](churn.md), escritos na Etapa 9.

---

## 7. O que estas perguntas deixam de fora

Registrado para que a ausência seja escolha, e não esquecimento:

- **Segmentação por valor de cliente (RFM).** Exige uma dimensão derivada que o modelo não declara.
  Fora do escopo da fase local.
- **Previsão e série temporal.** O Termo de Abertura não as inclui; o MVP entrega o dado que as
  tornaria possíveis, não os modelos.
- **Preço de tabela, contatos e preferências do cliente.** Nenhuma das 16 lê `price_lists`,
  `product_prices`, `customer_contacts` ou `customer_preferences`: a receita vem do preço
  **praticado**, que vive em `order_items` e não é cópia do preço de tabela
  ([Modelo de Dados §2.10](../modelo_de_dados.md#210-desvios-deliberados-da-3fn)), e nenhum recorte
  usa meio de contato ou consentimento. Por isso a origem `retail` não as ingere — tabela entra na
  ingestão quando um modelo a lê, regra que `test_toda_tabela_do_stream_tem_fonte_declarada_no_dbt`
  guarda. A origem legada captura as quatro, porque lá o que se reconcilia são as 40
  ([ADR-0037](../adr/0037-reter-capturas-do-legado-por-acrescimo.md)).
