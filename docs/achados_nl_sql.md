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
| Última atualização | 12/11/2026 (`nl_sql@e3ad98e`) |

---

## 1. Falhas deste projeto reveladas pelo teste

Cada item traz a evidência, o efeito, o que o `nl_sql` fez e **como replicar aqui**. Os achados
F1 a F4 vieram da revisão independente do Codex (`nl_sql/revisao_codex/REVISAO.md`); F5 a F10, da
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

### F5 — O glossário de receita líquida omite que só conta pedido realizado · **Gravidade: alta**

- **Evidência:** `docs/glossario_de_negocio/receita_liquida.md` define o cálculo sem mencionar
  `is_realised`. Todas as views de receita filtram `where f.is_realised`.
- **Efeito:** quem lê só o glossário, pessoa ou ferramenta, soma pedidos pendentes e cancelados. Foi
  o erro mais frequente do Gemini, em 4 de 19 perguntas (P01, P05, P06 e N1).
- **No `nl_sql`:** a métrica `receita_liquida` e o filtro `pedido_realizado` explicitam a regra e
  valem para todas as métricas de venda.
- **Replicar aqui:** acrescentar a regra ao glossário (receita líquida, ticket médio, lucro bruto) e à
  descrição de `net_revenue_amount`.

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
- **No `nl_sql`:** em andamento (`tabelas.yaml`).

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

## 2. Melhorias de governança do `nl_sql` replicáveis aqui

| Melhoria | No `nl_sql` | Equivalente aqui | Desvio |
|---|---|---|---|
| Domínios de valores com significado | `governanca/canonico/valores.yaml` | `accepted_values` + `{% docs %}` | Lá há também a versão em inglês, que aqui não existe (regra de idioma do `CLAUDE.md`) |
| Filtros nomeados | `canonico/filtros.yaml` | Glossário de negócio | — |
| Métricas estruturadas com SQL e verificação contra resultado esperado | `canonico/metricas.yaml` + `verificar_metricas.py` | Glossário estruturado, ou dbt *metrics* (ADR) | Lá a verificação é contra o gabarito do teste; aqui seria contra as views |
| Verificação automática "o dado tem valor fora da lista?" | `governanca/verificar.py` | `accepted_values` já faz parte disso | — |
| Ondas de criação por FK | `governanca/montar.py` | — (o dbt ordena por `ref`) | Só faz sentido com *constraints* declaradas |
| Descrição dentro do limite do BigQuery | renderizador (em construção) | Reescrever as descrições longas em vez de cortar | — |

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
