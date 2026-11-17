# Achados do nl_sql

> **O que vive aqui:** o que o **banco de provas NL→SQL** (projeto apartado `nl_sql`) descobriu e
> mudou, desde que clonou a informação deste projeto, escrito para ser **replicado aqui**, com o
> desvio de cada um. Primeiro as **falhas** deste projeto que o teste revelou; depois as
> **melhorias** de governança que o `nl_sql` construiu; por fim o **registro** cronológico.
>
> **O que não vive aqui:** o desenho do teste, as perguntas, o gabarito e os resultados das
> ferramentas (ver o repositório `nl_sql`, privado: `github.com/alencardoug/nl_sql`, em especial
> `README.md`, `PLANO.md` e `governanca/DESENHO.md`). Este documento **não altera nada**: cada item
> diz onde mexer aqui, mas a decisão e a implementação são do Owner, com ADR quando a mudança pedir.

| Campo | Informação |
|---|---|
| Origem do clone | Dados, `esquema.json` e gabarito do BigQuery `mvp-ed1-gcp` (`analytics`, views `consumption`), em 11/11/2026; dbt de `analytics`, glossário de negócio e modelo de dados deste repositório no commit `cbc5271`, em 12/11/2026 |
| Relação | O `nl_sql` é **dono da própria governança** e não recebe as mudanças daqui. Este documento é a via de volta: o que vale a pena trazer para cá |
| Como manter | Cada melhoria ou falha nova no `nl_sql` ganha uma entrada aqui, no mesmo dia, com o commit do `nl_sql` que a contém |
| Última atualização | 17/11/2026 (o ciclo do Bloco 5R: F22 e F24 a F27 conferidos no armazém); 16/11/2026 (F30, da validade da reserva no legado; F29, da cobertura da autorização pendente; as correções do F22 e do F24 a F27 no ramo do Bloco 5R); 15/11/2026 (F28, da aditividade declarada; F27, da revisão do Bloco 5R; F24 a F26, os significados do Bloco 5 medidos contra o dado; F22 e F23, achados ao desenhar o Bloco 5); 14/11/2026 (`nl_sql@ce09526`; F17 a F20 da auditoria das views daqui) |

---

## 1. Falhas deste projeto reveladas pelo teste

Cada item traz a evidência, o efeito, o que o `nl_sql` fez e **como replicar aqui**. Os achados
F1 a F4 vieram da revisão independente do Codex (`nl_sql/revisao_codex/REVISAO.md`); F5 a F16, da
construção da governança no `nl_sql`.

### F1 — `support_tickets_per_hundred_orders` perde parte do denominador · **Gravidade: alta**

- **Evidência:** `dbt/models/consumption/support_tickets_per_hundred_orders.sql:119–122`. A view
  parte dos chamados (`from chamados_por_mes t`) e recebe os pedidos por `sales_channel_key`
  (`left join pedidos_por_mes p`). A chave do canal é separada por origem. Quando uma origem não tem
  chamado numa categoria naquele mês, os pedidos dela não entram no denominador.
- **Efeito:** ao agrupar por **nome** do canal, 73 de 117 taxas ficam erradas. Exemplo: jan/2024,
  Conta, Aplicativo: o `retail` tem 22 pedidos realizados e 1 chamado, o `legacy` tem 1 pedido e
  nenhum chamado. A view dá 100/22 = **4,55**; o certo é 100/23 = **4,35**.
- **No `nl_sql`:** gabarito corrigido na v2. A métrica `chamados_por_100_pedidos` agrega chamados e
  pedidos **separadamente** no grão final (mês × canal pelo nome) e só então divide.
- **Replicar aqui:** reescrever a view para agregar numerador e denominador cada um no seu grão, e
  só então juntar, sem partir dos chamados. Regerar e conferir contra
  `nl_sql/governanca/canonico/metricas.yaml` (`chamados_por_100_pedidos`).
- **Desvio:** nenhum; a correção é a mesma.
- **Replicado aqui em `9aeea8d`** (14/11/2026): cada lado agregado no seu grão antes de dividir. Os
  chamados por mês × canal pelo nome × categoria; os pedidos por mês × canal pelo nome, somando as
  origens, repetidos em cada categoria. Jan/2024, Conta, Aplicativo: 4,5455 → 4,3478. Teste de unidade e reconciliação com as fatos.

### F2 — `inventory_turnover_by_sku_and_warehouse` mede outra grandeza · **Gravidade: alta**

- **Evidência:** `dbt/models/consumption/inventory_turnover_by_sku_and_warehouse.sql:12` anuncia
  "custo do que saiu ÷ valor médio em estoque". As linhas 56–58 usam
  `inventory_balances.quantity_on_hand × avg(unit_cost)`: o **saldo corrente**, sem recorte
  trimestral.
- **Efeito:** o giro do trimestre usa o saldo de hoje, então compras posteriores mudam o
  denominador de trimestres passados. A view também depende de `inventory_balances` e
  `inventory_movements`, que estão fora das 25 tabelas de `analytics`. Reconstruir o saldo pelos
  movimentos (`sum(quantity_delta)`) diverge em 12 de 5.669 linhas.
- **No `nl_sql`:** a pergunta P11 saiu do teste, que ficou com 19 perguntas.
- **Replicar aqui:** calcular o estoque **médio do período** (saldo inicial + movimentos, ou média
  de *snapshots*), ou renomear a métrica para o que ela é ("CMV do trimestre ÷ saldo corrente
  valorizado"). Exige decisão sobre a regra de valorização.
- **Desvio:** o `nl_sql` não corrige, apenas exclui.
- **Replicado aqui em `69ea446` e `9d50cca`** (14/11/2026), pelo ADR-0052: o estoque médio do trimestre
  (média diária da posição de fim de dia, a custo médio móvel, sem nada posterior), lido do livro em
  `analytics`. As colunas viraram `avg_quantity_on_hand` e `avg_inventory_value_amount`. O giro fica
  indefinido quando a posição de fim de dia é zero em todo o trimestre: dos 1.216 casos, 1.212 têm uma
  correção-relâmpago do gerador no trimestre (V4 das Pendências). A correção sozinha não anula o giro:
  114 trimestres com ela têm valor médio positivo.

### F3 — `dim_customer` e `fact_sales_order_item` discordam sobre a população · **Gravidade: média**

- **Evidência:** 15 clientes, todos `legacy`, têm 38 pedidos na dimensão contra 23 pedidos distintos
  na fato. Em 7 deles, a primeira compra também difere. Exemplo: o cliente `legacy` 21 tem a primeira
  compra em 10/03/2025 na dimensão e em 01/01/2026 UTC na fato. O cliente `legacy` 43 tem uma compra
  na dimensão e nenhuma na fato. As consultas estão em
  `nl_sql/revisao_codex/diagnosticos/P04_primeira_compra.sql`.
- **Efeito:** `first_order_at` e `is_repeat_buyer` da dimensão não reconciliam com a fato. A view
  `new_and_repeat_customers_by_month` usa a fato, e a dimensão documenta os mesmos conceitos.
- **No `nl_sql`:** a P04 aceita as duas leituras. A governança aponta para os campos da dimensão.
- **Replicar aqui:** achar a causa (quarentena, itens ausentes ou alguma transformação anterior) e
  reconciliar, ou documentar o recorte de cada fonte. Vale um teste de reconciliação dimensão × fato.
- **Desvio:** o `nl_sql` não reconcilia; ele aceita as duas leituras.
- **Diagnosticado aqui em `d212c07`** (14/11/2026): a causa é a regra do pai que sobrevive (D35). Os 15
  pedidos a mais da dimensão estão sem item aceito, com todos os itens na quarentena. A regra fica
  (Q7, decidida em 14/11/2026), com teste de reconciliação e a exceção declarada nas descrições.

### F4 — Descrições de coluna erradas ou cortadas · **Gravidade: média**

| Coluna | Problema | Onde |
|---|---|---|
| `dim_carrier.service_level` | A descrição herdada é a definição de **prazo prometido**, e não a da modalidade (`standard`, `express`, `same_day`) | `dbt/models/analytics/_analytics__models.yml:1681` (herdada) |
| `fact_cart_event.event_type` | Lista `open`, mas o dado tem `created` | `_analytics__models.yml:793` e `staging/_retail__sources.yml:565` |
| 4 colunas | Texto cortado com "[…] texto completo no catálogo (dbt docs)", porque o BigQuery aceita no máximo **1.024 caracteres** por descrição de coluna | `dbt/macros/descricao_no_bigquery.sql:20` |
| `fact_support_ticket_event` (tabela) | Manda contar `count(distinct support_ticket_id)`, sem a origem, o que contradiz a regra de identidade `(source_system, id)` | `_analytics__models.yml:2685` |

- **Efeito:** uma ferramenta NL→SQL que só lê o catálogo do BigQuery recebe uma definição errada, ou
  só metade dela.
- **No `nl_sql`:** correção na governança C1 (em andamento). O renderizador do BigQuery vai respeitar
  o limite de 1.024 caracteres **por construção**: texto curto e completo, em vez de longo e cortado.
- **Replicar aqui:**
  - corrigir as três descrições;
  - para as cortadas, reescrever uma versão curta (≤ 1.024) que se sustente sozinha, em vez de
    cortar o texto longo.
- **Replicado aqui em `4e163c9`** (14/11/2026): as três descrições corrigidas e, para as longas, a versão curta que o BigQuery recebe — o texto antes do marcador `<!-- bigquery: fim do texto curto -->` no glossário. `tests/test_descricao_no_bigquery.py` prova, sobre o *manifest*, que nenhuma coluna é cortada.

### F5 — O glossário de receita líquida omite que só conta pedido realizado · **Gravidade: alta**

- **Evidência:** `docs/glossario_de_negocio/receita_liquida.md` define o cálculo sem mencionar
  `is_realised`. Todas as views de receita filtram `where f.is_realised`.
- **Efeito:** quem lê só o glossário, pessoa ou ferramenta, soma pedidos pendentes e cancelados. Foi
  o erro mais frequente do Gemini, em 4 de 19 perguntas (P01, P05, P06 e N1).
- **No `nl_sql`:** a métrica `receita_liquida` e o filtro `pedido_realizado` explicitam a regra e
  valem para todas as métricas de venda.
- **Replicar aqui:** acrescentar a regra ao glossário (receita líquida, ticket médio, lucro bruto) e à
  descrição de `net_revenue_amount`.
- **Replicado aqui em `d3a9f9b`** (a regra no glossário, passo 1 do Bloco 1b) e conferido na versão curta em `4e163c9`.

### F6 — Sete FKs sem teste `relationships` no dbt · **Gravidade: média**

- **Evidência:** a verificação das métricas no `nl_sql` não achou caminho de `fact_sales_order_item`
  para `dim_brand`.

| FK sem teste | Conferida nos dados |
|---|---|
| `fact_sales_order_item.brand_key` → `dim_brand` | 0 órfãos em 7.738 |
| `fact_refund.customer_key` → `dim_customer` | 0 em 120 |
| `fact_refund.payment_method_key` → `dim_payment_method` | 0 em 120 |
| `fact_refund.sales_channel_key` → `dim_sales_channel` | 0 em 120 |
| `fact_payment_transaction.sales_channel_key` → `dim_sales_channel` | 0 em 7.426 |
| `fact_purchase_order_item.date_key` → `dim_date` | 0 em 1.630 |
| `fact_purchase_order_item.category_key` → `dim_category` | 0 em 1.630 |

- **No `nl_sql`:** estão em `governanca/canonico/relacionamentos.yaml`. O total vai de 44 para 51
  FKs, todas conferidas.
- **Replicar aqui:** acrescentar os 7 testes `relationships` em `_analytics__models.yml`.

### F7 — Colunas categóricas sem lista de valores nem significado · **Gravidade: média**

- **Evidência:** só 14 colunas têm `accepted_values`, e nenhuma lista diz o que cada valor significa.
  O `nl_sql` levantou 42 domínios, cobrindo 80 colunas, que precisam de significado: estados do
  pedido, da remessa, do chamado e do reembolso, tipos de transação, códigos do adquirente, tipos de
  movimento, membros "desconhecido" etc.
- **Efeito:** a ferramenta não sabe, por exemplo, que `returned` ainda é venda realizada, ou que
  `51` é saldo insuficiente.
- **No `nl_sql`:** `governanca/canonico/valores.yaml` tem os 42 domínios e 235 valores com
  significado em português e inglês, conferidos contra os dados, sem lacuna.
- **Replicar aqui:** `accepted_values` nas colunas que faltam, mais o significado num bloco
  `{% docs %}` ou em `meta`. Decidir o formato; mudar `meta` pode pedir ADR.

### F8 — Grão declarado em só 10 das 25 tabelas · **Gravidade: baixa**

- **Evidência:** as 10 fatos têm "**Grão:**" na descrição; as 15 dimensões não.
- **Replicar aqui:** declarar o grão de cada dimensão ("uma linha por versão do cliente", "uma linha
  por SKU-variante e versão"…).
- **Também:** `dim_brand`, `dim_category` e `dim_payment_method` não têm descrição de tabela nenhuma
  (`descricao_c0` vazia).
- **No `nl_sql`:** feito em `governanca/canonico/tabelas.yaml` (`nl_sql@f3b96fb`): grão das 25 tabelas, com a
  chave de negócio do grão conferida **única e sem nulo** nos dados (ex.: `dim_customer` =
  `(source_system, customer_natural_key, valid_from)`; `fact_cart_event` = `(source_system, cart_id, event_type)`),
  mais descrição, quando usar, quando não usar (com a tabela certa), versões e membros desconhecidos.
- **Replicado aqui em `b326c66`** (14/11/2026): o grão das 15 dimensões, com a chave de grão conferida única no armazém, e a descrição das três que não tinham.

### F9 — Regras de negócio que só existem dentro das views · **Gravidade: alta**

- **Evidência:** a verificação `nl_sql/governanca/verificar_metricas.py` mostrou que, para reproduzir
  o gabarito só com governança, foi preciso explicitar regras que este projeto só codifica no SQL de
  `consumption`:
  - conversão de carrinho = convertidos ÷ carrinhos **fechados**, pela data de **criação** do
    carrinho;
  - entrega no prazo por **remessa** (e não por item), pela data de **entrega**;
  - tempo do pedido até a entrega por **pedido**, na remessa que fecha o ciclo;
  - CMV em `fact_inventory_movement` (`is_sale`), pela data de **expedição**; a categoria vem do
    produto, porque o movimento não tem `category_key`;
  - reembolso ÷ capturado do **mês inteiro**, e não da transação reembolsada;
  - aprovação = autorizações aprovadas ÷ **tentativas de autorização**;
  - resgates de cupom **sem** filtro de pedido realizado;
  - clientes cadastrados = versão vigente e não excluídos.
- **No `nl_sql`:** `governanca/canonico/metricas.yaml` (30 métricas) e `filtros.yaml` (11 filtros).
  A verificação deu **23 de 23 gabaritos reproduzidos** só a partir dessas definições.
- **Replicar aqui:** trazer essas definições para o glossário de negócio, em forma estruturada
  (fórmula, numerador, denominador, filtro, data, grão). Uma camada semântica (dbt *metrics*) seria
  componente novo e pediria ADR.

### F10 — PK/FK existem só como teste, não como *constraint* · **Gravidade: média**

- **Evidência:** as chaves estão em testes `unique` e `relationships`, mas não chegam ao BigQuery
  como `PRIMARY KEY` / `FOREIGN KEY NOT ENFORCED`.
- **Efeito:** o Gemini (*data insights*), o Knowledge Catalog e o Genie no Databricks usam as
  *constraints* declaradas para descobrir as junções. Testes não chegam a eles.
- **No `nl_sql`:** o Terraform declara as 25 PKs e as 51 FKs a partir do nível C1, depois de
  `checar_chaves.py` provar nos dados que são verdadeiras (sem duplicata, sem órfão).
- **Replicar aqui:** *contract* + *constraints* nos modelos de `analytics`. É mudança de modelagem e
  pede ADR.

---

### F11 — A descrição de uma fato cita uma pergunta do teste · **Gravidade: baixa**

- **Evidência:** `dbt/models/analytics/_analytics__models.yml:1069` (`fact_payment_transaction`): "é a
  pergunta P09".
- **Efeito:** a governança aponta para uma pergunta de negócio pelo número; para uma ferramenta NL→SQL é
  ruído (ela não conhece "P09") e, num teste, é vazamento de pergunta para o metadado.
- **No `nl_sql`:** a descrição C1 da tabela não cita pergunta nenhuma; a regra (as recusas ficam na fato,
  para medir aprovação e tentativas) fica no texto, sem o número.
- **Replicar aqui:** trocar a citação pela regra que ela justifica.
- **Replicado aqui em `b326c66`**: a descrição diz a regra, sem o número da pergunta.

### F12 — Nada diz para agrupar pelo nome quando o mesmo membro existe nas duas origens · **Gravidade: média**

- **Evidência (dados de 11/11/2026):** o mesmo canal, categoria, meio de pagamento, transportadora,
  armazém, fornecedor e campanha aparecem nas duas origens com chaves diferentes (ex.: `Loja online`,
  `Pix`, `Panelas`, `CD Recife` têm uma linha `retail` e uma `legacy`). Já o código de SKU e de cliente
  repete-se entre origens para **entidades diferentes** (`SKU-0000029`, `CUS-0000024`).
- **Efeito:** a regra de identidade `(source_system, id)` está documentada, mas não o seu par: para
  recortar pelos atributos conformados, agrupa-se pelo **nome**. Agrupar pela chave parte "Loja online"
  em duas linhas; agrupar SKU pelo código junta dois itens diferentes.
- **No `nl_sql`:** `tabelas.yaml` declara o `rotulo` de agrupamento de cada dimensão conformada, e o
  `verificar.py` confere que o nome de fato se repete entre origens (reprovou `dim_brand`, onde não se
  repete).
- **Replicar aqui:** dizer na descrição de cada dimensão conformada por qual coluna agrupar, ao lado da
  regra de identidade.
- **Replicado aqui em `b326c66`**: cada dimensão conformada diz por qual nome agrupar; `dim_customer` e `dim_product` dizem que o código se repete entre origens para entidades diferentes (74 e 22 códigos, conferidos).

### F13 — `fact_shipment_item.date_key` não é só a data de despacho · **Gravidade: média**

- **Evidência:** `dbt/models/analytics/fact_shipment_item.sql:131` calcula a data com
  `coalesce(r.shipped_at, r.source_created_at)`; a descrição, em
  `dbt/models/analytics/_analytics__models.yml:1761`, diz "Data de **despacho** da remessa". Nos dados, 346 das
  7.556 linhas são de remessas não despachadas (`is_dispatched` falso), e nelas a data é a de criação.
- **Efeito:** "remessas despachadas por mês" pela `date_key` conta também as que ainda não saíram.
- **No `nl_sql`:** `tabelas.yaml` declara o significado de cada uma das 12 colunas-data das fatos e o
  `verificar.py` confere, linha a linha, que cada uma é a data local de São Paulo do instante declarado
  (só esta tem exceção, restrita a `is_dispatched`). A correção da descrição da coluna vai para
  `colunas.yaml`.
- **Replicar aqui:** corrigir a descrição ("despacho; na remessa ainda não despachada, a criação") ou
  separar as duas datas.
- **Replicado aqui em `b326c66`**: a descrição de `date_key` nas duas fatos de remessa diz a exceção da remessa não despachada.

### F14 — Duas descrições de `fact_refund` não dizem o que a coluna guarda · **Gravidade: média**

- **Evidência (`mvp_eng_dados_2@32397cc`):**
  - `dbt/models/analytics/_analytics__models.yml:1318`: `refunded_at` = "Momento em que o reembolso foi
    concluído". Nos dados de 11/11/2026, a coluna está preenchida nos 120 reembolsos, inclusive nos 8 solicitados
    e nos 2 recusados. O `date_key` sai dela (`dbt/models/analytics/fact_refund.sql:40`,
    `coalesce(r.refunded_at, r.source_created_at)`).
  - `_analytics__models.yml:1337`: `originally_captured_amount` = "Valor movimentado nesta operação". Na verdade
    é o `captured_amount` da transação de captura revertida (`fact_refund.sql:32`; 120/120 batem com
    `fact_payment_transaction.captured_amount`, e todas as transações revertidas são `capture`).
- **Efeito:**
  - "reembolsos concluídos por mês" pela data conta também os solicitados e os recusados;
  - a ferramenta não tem como saber que `originally_captured_amount` não é o capturado do período.
- **No `nl_sql`:** `governanca/canonico/colunas.yaml` corrige as duas (`nl_sql@ce09526`). O `verificar.py` passou a
  exigir correção para toda C0 sabidamente errada (F4 e F14).
- **Replicar aqui:**
  - `refunded_at`: "instante registrado do reembolso; preenchido também nos solicitados e recusados" (ou anular
    fora do concluído);
  - `originally_captured_amount`: "valor capturado na transação que este reembolso reverte".
- **Replicado aqui em `b326c66`**: `refunded_at` corrigido na declaração de origem (`models/payments.py`), e `originally_captured_amount` com texto próprio em `fact_refund`.

### F15 — Descrições apontam para o que não existe na camada `analytics` · **Gravidade: baixa**

- **Evidência (`mvp_eng_dados_2@32397cc`, `dbt/models/analytics/_analytics__models.yml`):**
  - `:667`, `:1878`, `:2105`: "o histórico vive em `order_status_history`", uma tabela da origem. Na
    `analytics`, o histórico é `fact_order_status_event`;
  - `:1419`, `:1834`: "transições válidas em Modelo de Dados §4";
  - `:2578`: "as três condições da invariante 12";
  - 76 citações de ADR, e referências a *macro*, *snapshot*, *seed* e Beam;
  - descrições de coluna que trazem o conceito inteiro do glossário, com a view `consumption` que o implementa
    (ex.: `dim_customer.is_repeat_buyer`).
- **Efeito:** quem lê só o catálogo (uma ferramenta NL→SQL, um analista no BigQuery) recebe uma referência que não
  consegue seguir. Ou recebe o caminho da view pronta, em vez da regra.
- **No `nl_sql`:** as colunas afetadas ganharam texto próprio (estão entre as 67 com texto próprio), e o `verificar.py` reprova jargão do MVP no texto
  resolvido de qualquer coluna.
- **Replicar aqui:** trocar a referência pela regra que ela abrevia ("o histórico está em
  `fact_order_status_event`"; "vigência, mínimo e limite").
- **Desvio:** os ADR continuam úteis no catálogo do dbt *docs*, que é para quem mantém o projeto. Tirá-los só da
  descrição que vai ao BigQuery já resolve.
- **Replicado aqui em `b326c66`**: o estado do pedido aponta para `fact_order_status_event`, os estados de remessa e de compra listam os valores, e o cupom diz as três condições. As citações de ADR ficam no catálogo (o desvio declarado acima).

### F16 — "Data de referência do **armazém**" é ambígua · **Gravidade: baixa**

- **Evidência (`mvp_eng_dados_2@32397cc`):** `dbt/models/analytics/_analytics__models.yml:185`, `:190`, `:696`,
  `:701`, `:812`, `:2206`, `:2211`, `:2335` falam em "data de referência do armazém (`as_of_date`, 01/09/2026)",
  no sentido de *data warehouse*. Na mesma camada, `dim_warehouse` é o "Armazém" físico (centro de distribuição).
- **Efeito:** em português, "armazém" lê-se como `dim_warehouse`. Uma ferramenta pode procurar a data num
  armazém.
- **No `nl_sql`:** "data de referência dos dados (01/09/2026)" nas 9 colunas.
- **Replicar aqui:** "data de referência dos dados" (ou "do *data warehouse*").
- **Replicado aqui em `b326c66`**: "data de referência dos dados" em todas as declarações.

### F17 a F20 — o que a auditoria das 16 views daqui achou (Bloco 1b, 14/11/2026)

Estes não vieram do `nl_sql`: são da auditoria das views deste repositório, pelos três critérios da
etapa 2.11 do `bi-como-codigo` (não aditividade, saldo que depende do tempo, população recortada). Cada
view foi comparada com uma referência independente e com a população da camada responsável
(`tests/test_auditoria_das_views.py`, `tests/auditoria/`). O resultado por view está em
`tests/auditoria/resultado.yml`. Entram aqui pela regra de entrada do plano, que os põe no mesmo
inventário.

### F17 — A P14 perdia o pedido cujos itens foram todos rejeitados · **Gravidade: média**

- **Evidência:** 13 pedidos do legado com todas as remessas entregues e nenhum item aceito (os itens
  na quarentena, em cascata) ficavam fora de `order_to_delivery_time_by_region`, que lia a fato de item.
  É o padrão da D66 no grão do pedido.
- **Corrigido aqui em `12677a3`**, por decisão do Owner de 14/11/2026: a view lê `fact_shipment`
  (ADR-0053). Pedidos: 2.761 → 2.774.

### F18 — A P04 perdia a estreia feita num pedido de itens rejeitados · **Gravidade: média**

- **Evidência:** a estreia saía da fato de item. Para o cliente cujo primeiro pedido teve todos os
  itens rejeitados, a view punha a estreia num mês mais tarde (6 clientes) ou não a contava (1), contra
  a `dim_customer` (F3, Q7).
- **Corrigido aqui em `12677a3`**, pela mesma decisão: a estreia e a recompra saem do grão do pedido,
  `fact_order_status_event`. Estreias: 1.388 → 1.389, iguais às da dimensão.

### F19 — Carrinho convertido sem item · **Gravidade: baixa (observação)**

- **Evidência:** a P07 conta os carrinhos com item, como o glossário define. Ficam de fora 145 sem item
  em `trusted.carts`, e 14 deles estão marcados como convertidos: um carrinho vazio que virou pedido.
- **Efeito:** nenhum na view. É incoerência do dado sintético, e fica como observação de realismo.

### F20 — O ranking da P03 se partiria se o produto mudasse de atributo · **Gravidade: baixa (observação)**

- **Evidência:** `top_skus_by_revenue` agrupa o SKU também por nome, categoria e marca da versão do
  produto. Um SKU que mudasse um desses atributos teria duas linhas e dividiria a receita no ranking.
  Hoje, 0 dos 595 SKUs vendidos têm mais de uma combinação.
- **Efeito:** nenhum no dado atual; risco latente, registrado. A referência da auditoria agrupa pela
  origem com a chave natural e marca o atributo como "VÁRIOS" se ele variar: se o F20 acontecer, ela
  diverge da view.

### F21 — O denominador de pedidos perdia o pedido de itens rejeitados · **Gravidade: média**

- **Evidência** (revisão da auditoria, RVB1b-1-01): a P15 contava os pedidos do denominador na fato de
  item, e os 15 pedidos realizados do legado cujos itens foram todos para a quarentena saíam dele (15
  combinações de mês e canal; 4 delas com chamado e linha na view).
- **Corrigido aqui**, pela regra do pai que conta (D66, Q7): o denominador sai do grão do pedido,
  `fact_order_status_event`, e a conferência de população o compara com `trusted.orders`.
- **Recorte declarado, não corrigido:** o `order_count` das views de receita (P01, P02, P05, P06) conta
  o pedido com item aceito, ao lado da receita do mesmo item. A receita do pedido de itens rejeitados
  não é conhecida, e contá-lo com receita zero baixaria o ticket médio da P02. A conferência de
  população da P02 declara a exceção.

### F22 — O código de retorno do adquirente não tem relação com o resultado · **Gravidade: média**

- **Evidência** (medida no armazém local em 15/11/2026, ao desenhar o Bloco 5): o gerador sorteia o
  `gateway_response_code` na lista `00`, `05`, `51`, `57`, `91`, `GW-OK`, `GW-TIMEOUT`
  (`generator/geracao.yml`, `payment_transactions`), sem olhar o resultado. Em
  `fact_payment_transaction`, o `51` — saldo insuficiente, pela convenção do mercado — aparece em 520
  autorizações aprovadas, o `00` em 30 recusadas, e o `GW-TIMEOUT` em 467 capturas bem-sucedidas; a
  distribuição dos resultados é a mesma para todo código, dentro da variação do sorteio.
- **Efeito:** uma ferramenta, ou uma pessoa, que leia o código pelo significado convencional explica a
  recusa errado. Foi o que o `nl_sql` declarou no F7 ("`51` é saldo insuficiente").
- **Aqui**, pela decisão do Owner (Q17 do plano da base dos consumidores): o domínio do código diz que
  ele não tem significado de negócio neste dado e que o resultado está em `transaction_result`; nenhum
  número muda. **Revisto em 15/11/2026** (Q26): a correção do gerador entra na regeneração do Bloco 5R, no
  fim da fase; o código passa a seguir o resultado, e o significado de cada código vira proposta para o
  aceite do Owner. Até o ciclo, o domínio declara o que a Q17 decidiu. **No ramo `bloco-5r` (16/11/2026):** o mapa aceito
  (Q41) está em `generator/geracao.yml` — `succeeded` → `00`, `pending` → `GW-OK`, `failed` → um dos cinco
  motivos de recusa, por peso —, guardado pela invariante 19 do Modelo de Dados §4. No varejo, as 7.102
  transações seguem o mapa: 3.381 autorizações e todas as capturas, estornos e reembolsos com `00`, 74
  pendentes com `GW-OK`, 212 recusadas entre `51`, `05`, `57`, `91` e `GW-TIMEOUT`. Medido em memória no gerador corrigido e, depois do ciclo do Bloco 5R (17/11/2026), no armazém, nas duas origens: a guarda `invariante_19_codigo_do_adquirente_segue_o_resultado` passa.

### F23 — As tabelas das Perguntas de Negócio divergem das views · **Gravidade: média**

- **Evidência** (revisão do desenho do Bloco 5, RVB5-2-02, conferida aqui em 15/11/2026): a tabela da P07
  lista `cart_conversion_rate` e `abandoned_cart_value`, e as colunas da view são `cart_conversion_rate_pct`
  e `abandoned_value_amount`; a da P08 aponta `fact_purchase_order_item`, e o CMV da view vem de
  `fact_inventory_movement`; a da P11 ainda tem `quantity_on_hand`, que a ADR-0052 trocou pela média do
  trimestre (`perguntas_de_negocio.md:129`, `:154`, `:195`).
- **Efeito:** o pacote de metadados publica essas tabelas em `questions.*.facts` e `questions.*.measures`;
  um portal, ou uma ferramenta, que procure a medida pelo nome não a acha, ou acha a fato errada.
- **Aqui:** no Bloco 5, a tabela de cada pergunta passa a ser gerada da declaração das métricas
  (`metricas.yml`), com os nomes físicos; o texto da pergunta fica à mão.

### F24 — O estado do cliente e o do produto não têm relação com a venda · **Gravidade: média**

- **Evidência** (medida no armazém local em 15/11/2026, ao medir os significados do Bloco 5 contra o dado):
  dos pedidos realizados, 165 são de cliente `pending` e 150 de cliente `blocked`, na versão da dimensão
  que a fato aponta; dos itens de pedido realizado, 51 são de produto `draft` e 96 de produto
  `discontinued`. Nenhum cliente nem produto tem mais de uma versão, então o estado já era esse na venda.
  As duas origens têm o caso (`retail`: 161 e 143 pedidos, 48 e 77 itens; `legacy`: 4 e 7, 3 e 19). A
  causa: o gerador sorteia o estado por peso (`generator/geracao.yml`, `customers` e `products`) e escolhe
  o cliente e a variante do pedido entre todos (`generator/domains/vendas.py`), sem olhar o estado.
- **Efeito:** o significado aceito pelo Owner (Q19) — `pending` é cadastro não concluído, `blocked` é
  cliente impedido de comprar, `draft` é produto não publicado — é desmentido pelo próprio dado; quem
  filtra a venda pelo estado conclui que a empresa vende a quem não pode comprar.
- **Aqui**, pela decisão do Owner (Q21 e Q23 do plano da base dos consumidores): corrigir o gerador e
  regerar as duas origens, no Bloco 5R — uma regeneração só, no fim da fase (Q25); os números das views
  mudam. **No ramo `bloco-5r` (16/11/2026):** os candidatos de carrinho e de pedido passam a ser escolhidos pelo instante do
  evento, e a variante inativa segue a regra do `discontinued` (Q39); invariante 15. No varejo, nenhum
  pedido nem carrinho identificado de `pending` ou `blocked`, nenhum item de `draft`, e nenhuma venda de
  `inactive`, de `discontinued` ou de variante inativa dentro da janela; os 25 produtos `discontinued`
  continuam com venda antiga, e 193 dos 210 clientes `inactive`, com pedido antigo. Medido em memória no gerador corrigido e, depois do ciclo do Bloco 5R (17/11/2026), no armazém, nas duas origens: a guarda `invariante_15_cadastro_respeitado_no_tempo` passa.

### F25 — A remessa extraviada aparece em pedido entregue · **Gravidade: média**

- **Evidência** (a mesma medida): 13 remessas `lost` estão em pedido `delivered`; em 9 delas o pedido não
  tem nenhuma remessa entregue. Todas são do `retail`. A causa: o laço de `remessas`
  (`generator/domains/logistica.py`) troca por `lost` a remessa sorteada como `delivered` — o contrário do
  que a *docstring* de `_garantir_extravio`, logo abaixo, diz evitar ("não de uma entregue, que seria
  contradição com o estado do pedido"). À parte, uma remessa do `legacy` (`SHP-00000081`) está
  `returned` sem evento de devolução no livro de entrega: os eventos dela terminam em `delivered`. Não é
  defeito do gerador: o catálogo do legado injeta `FK_ORPHAN` no `shipment_id` do evento de devolução
  (`81` → `952899`), e a limpeza o rejeita (revisão do Bloco 5R, RVB5R-1-06).
- **Efeito:** o pedido diz que chegou e nenhuma remessa dele chegou; a pontualidade e o ciclo de entrega
  (P13, P14) contam um pedido cuja entrega não existe.
- **Aqui**, pela decisão do Owner (Q22 e Q24): corrigir o gerador e regerar, no Bloco 5R, no fim da fase
  (Q25). **No ramo `bloco-5r` (16/11/2026):** o extravio sai das remessas em trânsito, com o volume mantido (Q43) — 0,4% de
  todas as despachadas; invariante 16. No varejo, 14 remessas `lost`, todas em pedido `shipped` (antes, 13,
  todas em pedido `delivered`). Medido em memória no gerador corrigido e, depois do ciclo do Bloco 5R (17/11/2026), no armazém, nas duas origens: a guarda `invariante_16_extravio_so_em_transito` passa.

### F26 — O chamado é reaberto sem ter sido resolvido · **Gravidade: baixa**

- **Evidência** (a mesma medida): os 14 chamados com evento `reopened` não têm evento `resolved` antes
  dele, e todos estão `in_progress`; e o chamado `resolved` tem `closed_at` preenchido, como o `closed`
  (`is_closed` verdadeiro nos dois). Todos são do `retail`. A causa: `_eventos`
  (`generator/domains/atendimento.py`) acrescenta o `reopened` ao chamado em andamento sem a resolução
  anterior, e o `closed_at` é preenchido para os dois estados de `_ENCERRADOS`.
- **Efeito:** a reabertura, que pelo significado aceito (Q19) é a de um chamado já resolvido, não tem o
  que reabrir; e o `resolved` não se distingue do `closed` pelo dado, embora o significado diga que ainda
  não foi fechado.
- **Aqui**, pela decisão do Owner (Q22 e Q24): corrigir o gerador e regerar, no Bloco 5R, no fim da fase
  (Q25). **No ramo `bloco-5r` (16/11/2026):** os eventos obrigatórios entram antes dos opcionais, e o `closed_at` fica só no
  `closed`; invariante 17. No varejo, os 15 chamados reabertos têm o `resolved` antes do `reopened`, nenhum
  `resolved` ou `closed` fica sem o evento de resolução, e os 94 `resolved` têm `closed_at` nulo. Medido em memória no gerador corrigido e, depois do ciclo do Bloco 5R (17/11/2026), no armazém, nas duas origens: a guarda `invariante_17_livro_do_chamado_acompanha_o_estado` passa.

### F27 — A reserva de estoque não é de um item do carrinho nem do pedido · **Gravidade: baixa**

- **Evidência** (medida na origem principal, `oltp`, em 15/11/2026, na revisão do Bloco 5R, RVB5R-1-01):
  das 4.200 reservas, só 12 são de um SKU que está no carrinho ou no pedido a que pertencem; 202 são de
  produto `draft` e 323 de `discontinued`. A causa: `_reservas` (`generator/domains/estoque.py`) sorteia o
  par armazém × variante entre todos os que têm movimento e, à parte, o carrinho ou o pedido, sem ligar um
  ao outro.
- **Efeito:** a reserva ocupa saldo de um item que ninguém pediu. A `CHECK origem_unica` garante que ela
  é de um carrinho **ou** de um pedido, não que o SKU seja de um item dele — é uma relação a mais, que não
  é a invariante 8 (a reserva encerrada fora do saldo reservado, Modelo de Dados §4, que vale). O livro de
  estoque não muda: as reservas nascem depois dos movimentos. O efeito está na projeção — o reservado e o
  disponível de `trusted.inventory_balances`, pelas reservas `active` —, e chega à P12, que desconta o
  reservado no filtro de reposição, no `is_stockout` e nos dias de cobertura. A tabela das reservas não
  vira fato em `analytics` (revisão do Bloco 5R, RVB5R-2-01 e 02).
- **Aqui**, pela decisão do Owner (Q28 do plano da base dos consumidores): a reserva passa a ser de um SKU
  do carrinho ou do pedido dela, no Bloco 5R, no fim da fase. **No ramo `bloco-5r` (16/11/2026):** a reserva nasce de um item, com
  o SKU e a quantidade dele (Q40), no máximo uma por item; invariante 18. No varejo, as 4.200 reservas são
  de um item da própria origem; a divisão efetiva entre carrinho e pedido, que não é a declarada (Q45),
  está medida na [Geração de Dados §4.3](geracao_de_dados.md#43-onde-os-números-vivem). Medido em memória no gerador corrigido e, depois do ciclo do Bloco 5R (17/11/2026), no armazém, nas duas origens: a guarda `invariante_18_reserva_e_de_um_item_da_origem` passa.

### F28 — A contagem de pedidos da P06 se diz aditiva e se repete entre categorias · **Gravidade: baixa**

- **Evidência** (medida no armazém local em 15/11/2026, ao declarar a aditividade das métricas do Bloco 5,
  `bloco5_aditividade_order_count_20261115.txt`): a soma de `order_count` em `discount_share_by_channel` dá
  5.826 contra 3.292 pedidos realizados distintos; o pedido com itens de duas categorias raiz conta nas duas.
  A descrição da coluna diz "Aditiva — pedidos realizados distintos […], por canal e mês", mas o grão da view
  tem também a categoria raiz. Na P01 a mesma contagem já se diz "Não aditiva entre categorias"; na P02 e na
  P05, que não agrupam por categoria, a soma dá os 3.292, e "Aditiva" está certo.
- **Efeito:** quem soma a coluna pelas categorias, como a descrição autoriza, conta pedidos a mais.
- **Aqui:** a descrição passa a "Não aditiva entre categorias", como a da P01, e o grão certo; e a aditividade
  de cada coluna das views passa a ser declarada no `metricas.yml` e conferida contra o começo da descrição
  (Bloco 5, Parte B, a tabela gerada das perguntas). Muda o texto, não o valor nem o esquema.

### F29 — A autorização pendente some quando os pedidos em aberto são poucos · **Gravidade: baixa**

- **Evidência** (medida em memória em 16/11/2026, ao conferir a cobertura da invariante 19 no perfil de que
  o legado parte — fator 0,05, semente do catálogo de falhas): o perfil tem 3 pedidos em aberto, e os 3
  pagamentos deles saíam `authorized`; nenhuma transação com resultado `pending`, e já era assim antes do
  Bloco 5R. A causa: `_desfecho` (`generator/domains/pagamentos.py`) sorteia meio a meio entre `pending` e
  `authorized`, sem garantir os dois.
- **Efeito:** um valor de enumeração cuja presença depende da semente, contra a cobertura em qualquer
  fator do ADR-0014; e, com o mapa do F22, o `GW-OK` não apareceria no legado.
- **Aqui**, pela decisão do Owner (Q46 do plano da base dos consumidores): entra na fila do Bloco 5R. No
  ramo `bloco-5r` (16/11/2026), o gerador garante os dois desfechos em qualquer fator e semente — o sorteio
  só cede quando os pedidos em aberto que restam são tantos quantos os desfechos que faltam, e `orders`
  tem piso de oito linhas, com dois pedidos em aberto garantidos (Q54) —, e a invariante 19 exige os três
  resultados em todo perfil. No perfil do legado muda uma linha (uma
  autorização passa de aprovada a pendente); no varejo, nenhuma.

### F30 — A limpeza do legado trata a validade da reserva como fato consumado · **Gravidade: média**

- **Evidência** (16/11/2026, na sequência de testes do ramo do Bloco 5R): `DATE_FUTURE` — data posterior
  ao corte em campo de fato já ocorrido — vale para `stock_reservations.expires_at`, que é prazo: a reserva
  ativa no corte vence até 48 h depois dele. Em memória, o perfil de que o legado parte tem 4 reservas
  vencendo depois do corte com o gerador do ramo, e a limpeza rejeitava 3 delas sem que nenhuma falha
  tivesse sido injetada; com o gerador de antes, nenhuma — acaso da semente, porque o varejo tem 33.
- **Efeito:** reserva íntegra iria para a quarentena por um defeito que não tem, e o saldo reservado do
  legado perderia as reservas mais recentes.
- **Aqui**, pela decisão do Owner (Q48 do plano da base dos consumidores): a coluna entra nas `promessas`
  do catálogo de falhas (`legacy/catalogo.yml`, versão 10), como `carts.expires_at`; os modelos de limpeza
  são regenerados dele. O lote de hoje não tem o caso: o `make dbt-build` de 16/11/2026 retratou a captura
  corrente sob a versão 10 com o mesmo resultado linha a linha; o lote novo chega com o ciclo do Bloco 5R.

## 2. Melhorias de governança do `nl_sql` replicáveis aqui

| Melhoria | No `nl_sql` | Equivalente aqui | Desvio |
|---|---|---|---|
| Domínios de valores com significado | `governanca/canonico/valores.yaml` | `accepted_values` + `{% docs %}` | Lá há também a versão em inglês, que aqui não existe (regra de idioma do `CLAUDE.md`) |
| Filtros nomeados | `canonico/filtros.yaml` | Glossário de negócio | — |
| Métricas estruturadas com SQL e verificação contra resultado esperado | `canonico/metricas.yaml` + `verificar_metricas.py` | Glossário estruturado, ou dbt *metrics* (ADR) | Lá a verificação é contra o gabarito do teste; aqui seria contra as views |
| Verificação automática "o dado tem valor fora da lista?" | `governanca/verificar.py` | `accepted_values` já faz parte disso | — |
| Ondas de criação por FK | `governanca/montar.py` | — (o dbt ordena por `ref`) | Só faz sentido com *constraints* declaradas |
| Descrição dentro do limite do BigQuery | renderizador (em construção) | Reescrever as descrições longas em vez de cortar | — |
| Descrição de coluna por precedência (própria > padrão por família > original), com verificação de limite, jargão e correção obrigatória da original errada | `canonico/colunas.yaml` + `verificar.py` | Um `{% docs %}` por família (chave substituta, vigência, exclusão lógica) e um teste que lê o `manifest.json` | — |
| Ficha de tabela verificada nos dados (grão único, significado de cada data, versões, rótulo, membro desconhecido) | `canonico/tabelas.yaml` + `verificar.py` | Descrição de tabela do dbt + testes `unique_combination_of_columns` e um teste de data local por fato | Lá a verificação lê o Parquet congelado; aqui seria teste dbt |

---

## 3. Desvios deliberados (o que o `nl_sql` faz e não deve ser copiado aqui)

- **Só as 25 tabelas base** no teste: as views `consumption` não sobem, porque o teste mede geração
  de SQL e não busca de view pronta.
- **Pergunta P11 retirada** (por F2), e **gabarito v2** com leituras alternativas aceitas (P04, N5,
  P16).
- **Governança em inglês** derivada da portuguesa, para o conjunto de perguntas em inglês. Os dados
  continuam em português.
- **Datas de referência:** o `nl_sql` congelou os dados de 11/11/2026. Mudanças posteriores daqui não
  chegam lá.

---

## 4. Registro

| Data | Commit `nl_sql` | O que mudou | Itens |
|---|---|---|---|
| 11/11/2026 | `3d0f316` | Primeira medição (Gemini no BigQuery Studio, 5/20) e revisão do Codex: gabarito v2 com 19 perguntas | F1, F2, F3, F4 |
| 12/11/2026 | `b575b98` | Desenho da governança por plataforma; importação única deste projeto (`cbc5271`); PK/FK conferidas nos dados | F10 |
| 12/11/2026 | `018265c` | Valores com significado, filtros, métricas verificadas contra o gabarito (23/23), 7 FKs novas | F5, F6, F7, F9 |
| 12/11/2026 | `e3ad98e` | `nl_sql` com ambiente próprio, sem depender deste projeto; origem do clone registrada | — |
| 12/11/2026 | (este documento) | Limite de 1.024 caracteres por descrição como causa das descrições cortadas; grão das dimensões | F4, F8 |
| 13/11/2026 | `f3b96fb` | `tabelas.yaml`: grão, uso e datas das 25 tabelas, conferidos nos dados; canal de volta passa a ser este repositório (D92) | F8, F11, F12, F13 |
| 14/11/2026 | `ce09526` | `colunas.yaml`: texto das 477 colunas com as correções da original; decisões da resposta central (Q14) | F14, F15, F16 |
