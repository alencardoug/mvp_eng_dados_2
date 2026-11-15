# Taxa de conversão

{% docs cart_conversion_rate %}

**Taxa de conversão** é a fração dos carrinhos com item que resultaram em pedido, no mesmo recorte.

- **Cálculo:** `converted_cart_count / closed_cart_count`, **recalculado a cada
  recorte**: os convertidos sobre os carrinhos **fechados** (convertidos ou
  abandonados), pela data de **criação** do carrinho.
- **Implementado em:** view `cart_conversion_rate_by_channel`.
- **Relacionado:** carrinho abandonado, ticket médio.

<!-- bigquery: fim do texto curto -->

**É medida não aditiva**, pelo mesmo motivo do ticket médio: taxas não se somam. A view entrega
numerador e denominador ao lado do resultado.

**O carrinho é contado no mês em que foi criado**, não no mês em que converteu. Um carrinho aberto
em 30 de novembro e convertido em 2 de dezembro pertence a novembro nas duas contagens — senão a
taxa de dezembro poderia passar de 100%.

Carrinhos ainda **abertos e dentro do prazo** ficam fora do denominador: o desfecho deles ainda não
existe, e incluí-los faria a taxa dos meses recentes cair sozinha com o passar dos dias.

<!-- gerado a partir dos modelos; não editar à mão -->
**Como as views o contam** (gerado de `docs/glossario_de_negocio/metricas.yml`; a definição e o porquê ficam no texto acima):

- `converted_cart_count`: soma de `f.converted_cart_count`, em `analytics.fact_cart_event`, pela criação do carrinho. Aditiva.
- `closed_cart_count`: soma de `f.closed_cart_count`, em `analytics.fact_cart_event`, pela criação do carrinho. Aditiva.
- `cart_conversion_rate_pct` = 100 × `converted_cart_count` ÷ `closed_cart_count`, arredondada a 2 casas; nula com o denominador zero. Não aditiva.
<!-- fim do trecho gerado -->

{% enddocs %}
