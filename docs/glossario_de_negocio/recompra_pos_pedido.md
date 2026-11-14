# Recompra pós-pedido

{% docs post_order_repeat_purchase %}

**Recompra pós-pedido** é a fração dos pedidos após os quais o cliente fez outro
pedido em até **90 dias**, contados de `placed_at`. A unidade de contagem é o
**pedido**.

- **Cálculo:** `repeat_order_count / order_count`, sobre pedidos realizados cuja
  janela de 90 dias já fechou.
- **Só pedido realizado conta, dos dois lados:** o de partida e o pedido seguinte.
  Cancelado não é compra nem retorno.
- **Janela aberta fica de fora** do numerador e do denominador: o pedido cujos 90
  dias não fecharam em `as_of_date` não é ausência de recompra.
- **Implementado em:** `trusted.orders`, colunas `has_post_order_repeat`,
  `days_to_next_order` e `is_repeat_window_closed`; view
  `repeat_purchase_rate_after_support`.
- **Relacionado:** recorrência de compra, churn.

<!-- bigquery: fim do texto curto -->

**Não é a recompra de P04.** Aquela conta **clientes** de uma coorte de estreia —
quem comprou pela primeira vez em janeiro voltou até abril? Esta conta
**pedidos** — depois deste pedido, houve outro em 90 dias? Os dois números nunca
se somam, e dividir um pelo outro não produz nada.

A razão de o conceito existir é a P16
([ADR-0036](../adr/0036-recompra-ancorada-no-pedido.md)): comparar quem abriu
chamado com quem não abriu exige que os dois grupos tenham a **mesma âncora**. A
estreia do cliente não serve, porque o chamado pode ter vindo muito depois de a
janela fechar; o chamado não serve, porque quem não abriu chamado não tem esse
marco. O pedido serve para os dois.

**Por que os dois lados.** Contar o pedido cancelado como retorno diria que o
cliente voltou quando ele desistiu.

**Por que a janela fechada.** Sem ela, a taxa dos meses recentes cairia sozinha à
medida que o período avança — não porque os clientes voltaram menos, mas porque
ainda não tiveram tempo.

{% enddocs %}
