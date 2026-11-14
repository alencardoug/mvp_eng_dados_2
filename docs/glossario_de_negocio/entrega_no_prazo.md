# Entrega no prazo

{% docs on_time_delivery %}

**Entrega no prazo** é a remessa cuja chegada não é posterior à promessa que ela
carregava: `delivered_at <= estimated_delivery_at`. O grão é a **remessa**, não
o pedido.

- **Cálculo:** `on_time_count / delivered_count`, por transportadora, modalidade
  e mês de chegada.
- **A chegada vem do livro de eventos:** o evento `delivered` **mais recente** da
  remessa (ADR-0034), não o `delivered_at` corrente da origem, que é sobrescrito.
- **O denominador é o entregue, não o despachado.** Em trânsito ainda não chegou;
  extraviada nunca entra. **Devolvida conta:** chegou, e no prazo em que chegou.
- **Implementado em:** view `on_time_delivery_rate_by_carrier`, coluna
  `on_time_rate`, lida de `fact_shipment` (uma linha por remessa, ADR-0053);
  sinalizador `is_on_time` em `trusted.shipments`, `fact_shipment` e
  `fact_shipment_item`.
- **Relacionado:** ciclo de entrega, prazo prometido.

<!-- bigquery: fim do texto curto -->

**Por que o entregue.** Remessa em trânsito ainda não está atrasada. Contá-la
como fora do prazo trocaria "não chegou ainda" por "chegou tarde", que são coisas
diferentes e levam a decisões diferentes.

**O grão é a remessa porque a promessa é da remessa.** Transportadora e
modalidade são atributos de quem leva a caixa, e um pedido dividido em duas
remessas tem duas promessas — possivelmente de modalidades diferentes. Ele conta
**duas vezes** aqui, e é o comportamento correto: foram duas promessas e duas
chegadas. Quem quer a experiência do pedido inteiro usa o *ciclo de entrega*, que
é outro conceito e não se soma a este.

**Por que o livro de eventos.** A coluna da origem guarda o estado corrente; o
livro guarda o momento em que a chegada aconteceu. Medir prazo histórico contra a
coluna é medir contra o último `update`.

**Por que a devolvida conta.** Ela registra `delivered` e depois `returned`: a
devolução não desfaz a entrega, é fato posterior, contado à parte.

{% enddocs %}

{% docs promised_lead_time %}

**Prazo prometido** é a data até a qual a remessa deveria chegar, fixada no
despacho pela modalidade da transportadora que a leva —
`shipments.estimated_delivery_at`.

É **promessa, não evento**: pode estar no futuro sem que isso seja data
inconsistente, e não muda depois de feita. É contra ela, e não contra uma média
histórica, que a pontualidade é medida.

{% enddocs %}
