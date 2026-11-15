# Ciclo de entrega

{% docs order_to_delivery_cycle %}

**Ciclo de entrega** é o tempo entre o pedido feito e a chegada da **última**
remessa dele: de `placed_at` até `max(delivered_at)` das suas remessas. O grão é
o **pedido**.

- **Cálculo:** média de `order_to_delivery_days` sobre pedidos com ciclo fechado,
  por região de entrega, modalidade e mês de chegada.
- **A modalidade é a da remessa que fechou o ciclo**, a última a chegar — também
  no pedido dividido entre transportadoras.
- **Implementado em:** view `order_to_delivery_time_by_region`, coluna
  `avg_order_to_delivery_days`, lida de `fact_shipment` (ADR-0053); medida
  `order_to_delivery_days` em `fact_shipment` e `fact_shipment_item`.
- **Relacionado:** entrega no prazo, prazo prometido.

**Pedido sem ciclo fechado fica de fora.** Se qualquer remessa do pedido ainda
está em trânsito, foi extraviada ou nunca saiu, o pedido não tem tempo até a
entrega — tem tempo até agora, que é outra medida. Excluí-lo é o que impede a
média de **melhorar** quando uma remessa se perde.

<!-- bigquery: fim do texto curto -->

**O ciclo fecha na última remessa porque é quando o pedido chegou inteiro.** Um
pedido dividido em duas caixas não está entregue quando a primeira chega — está
pela metade. Medir pela primeira daria uma média sistematicamente otimista, e o
erro cresceria com a fração de pedidos divididos.

**Por que a modalidade da última.** É a única atribuição defensável quando um
pedido viaja por duas transportadoras: foi ela que determinou quando o pedido
ficou completo.

**Não se cruza com a entrega no prazo.** Aquela conta remessas e esta conta
pedidos (ADR-0033). Um pedido com uma remessa entregue e outra extraviada aparece
lá e não aparece aqui — as duas medidas nem sempre contam a mesma população, e
somá-las ou dividi-las uma pela outra produz número sem significado.

<!-- gerado a partir dos modelos; não editar à mão -->
**Como as views o contam** (gerado de `docs/glossario_de_negocio/metricas.yml`; a definição e o porquê ficam no texto acima):

- `avg_order_to_delivery_days`: média de `f.order_to_delivery_days`, arredondada a 4 casas, em `analytics.fact_shipment`, pela data da entrega. Só o pedido de ciclo fechado, na remessa que fechou o ciclo. Não aditiva.
- `median_order_to_delivery_days`: mediana de `f.order_to_delivery_days`, arredondada a 4 casas, em `analytics.fact_shipment`, pela data da entrega. Só o pedido de ciclo fechado, na remessa que fechou o ciclo. Não aditiva.
- `max_order_to_delivery_days`: máximo de `f.order_to_delivery_days`, arredondada a 4 casas, em `analytics.fact_shipment`, pela data da entrega. Só o pedido de ciclo fechado, na remessa que fechou o ciclo. Não aditiva.
<!-- fim do trecho gerado -->

{% enddocs %}
