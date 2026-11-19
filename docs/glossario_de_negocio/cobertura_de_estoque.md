# Cobertura de estoque

{% docs days_of_cover %}

**Cobertura de estoque** é por quantos dias o saldo disponível de um SKU dura ao
ritmo da demanda recente. Responde "quanto tempo eu tenho", que é a pergunta que
o comprador faz — e não "quanto eu tenho", que é a que o saldo responde.

- **Cálculo:** `quantity_available ÷ demanda diária média`, onde a demanda é a
  média das unidades **vendidas** por dia na janela de cobertura declarada em
  `dbt_project.yml`.
- **Implementado em:** view `skus_below_reorder_point`.
- **Relacionado:** ruptura de estoque, giro de estoque, ponto de reposição.

**Cobertura indefinida não é cobertura zero.** SKU sem venda na janela não tem
cobertura de zero dias: ele tem cobertura indeterminada, porque não há ritmo
contra o qual medir. A view devolve nulo, e escrever zero diria que o estoque
acaba hoje.

<!-- bigquery: fim do texto curto -->

**Só venda conta como demanda.** Transferência entre armazéns e devolução ao
fornecedor também tiram unidades do armazém, e nenhuma das duas é demanda de
cliente. Somá-las encurtaria a cobertura e faria o alerta disparar antes da hora,
sobre um consumo que não vai se repetir.

**Cobertura é razão, e razão não se soma.** É **não aditiva**: a cobertura de
dois SKUs não é a soma das duas, nem a média delas — quem reagregar precisa
refazer a conta a partir do saldo e da demanda, que por isso vão ao lado dela na
view.

{% enddocs %}

{% docs reorder_point %}

**Ponto de reposição** é o saldo disponível abaixo do qual é hora de comprar de
novo um SKU num armazém: a demanda esperada durante o prazo de reposição, mais
uma margem. Abaixo dele, o que resta acaba antes de a compra chegar.

- **Cálculo:** `teto(venda da janela ÷ dias da janela × (prazo + margem))`, por
  armazém e SKU. A venda é a saída por venda dos últimos 365 dias; o prazo, 28
  dias, a mediana medida do pedido ao primeiro recebimento; a margem, 14 dias.
  Os três são declarados em `dbt_project.yml` (ADR-0057).
- **Implementado em:** dimensão `dim_sku_location`, lida pela view
  `skus_below_reorder_point` e pelo alerta de estoque baixo do *streaming*.
- **Relacionado:** cobertura de estoque, ruptura de estoque.

**A janela é de um ano, e não a da cobertura.** O SKU em ruptura não vende, e
numa janela curta a ruptura longa zeraria a demanda dele, e com ela o ponto,
justamente quando ele mais precisa de reposição.

**O ponto é o do último lote.** Ele é calculado sobre os movimentos que o lote já
absorveu, e muda a cada processamento. O saldo da view muda a cada evento.

{% enddocs %}
