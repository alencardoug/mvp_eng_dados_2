# Consumidores

> **O que vive aqui:** quem lê este repositório, como lê, como pede o banco, por onde fala com ele e o
> que mudou para quem lê. É o canal de saída daqui para os consumidores, versionado para que cada um
> fixe o *commit* que leu.
>
> **O que não vive aqui:** a decisão de onde os consumidores leem (ver
> [D92](pendencias.md#d92--o-projeto-continua-no-mvp_eng_dados_2-e-o-mvp_eng_dados_1-fica-travado-decidida-em-13112026));
> o formato do pacote (ver [Pacote de Metadados](pacote_de_metadados.md)); o trabalho da fase que
> corrige o que eles leem (ver o [plano da base dos consumidores](../PLANO_base_dos_consumidores.md));
> os achados que o `nl_sql` devolve (ver [Achados do nl_sql](achados_nl_sql.md)).

| Campo | Informação |
|---|---|
| Aberto em | 14/11/2026, no alinhamento central das pendências dos três consumidores |
| Situação | Vigente |

---

## 1. Quem lê

| Consumidor | O que é | O que lê daqui | Por onde fala com cá |
|---|---|---|---|
| `nl_sql` (`~/Projetos/data/nl_sql`, privado) | Bancada de testes NL→SQL | Nada no ambiente. A importação é única e congelada (dados de 11/11/2026; dbt e glossário de `mvp_eng_dados_1@cbc5271`). Daqui só lê arquivos, para citar evidência `arquivo:linha` | Escreve as entradas nos [Achados](achados_nl_sql.md), sem *commit*; o Owner revisa e *commita* |
| `gdados` (`~/Projetos/gdados`) | Portal de leitura da governança, com estrutura, ambientes e conceitos | O pacote e os artefatos por *commit*. Não lê banco | `docs/alinhamento_entre_projetos.md`, no próprio repositório |
| `bi-como-codigo` (`~/Projetos/bi-como-codigo`, público) | Vitrine de BI como código, com o portal da etapa 2.7 | As views de `consumption`, pelo login `consumption_reader`; o pacote; os artefatos por *commit* | `docs/upstream_questions.md`, no próprio repositório |

O `gdados` e a etapa 2.7 do BI são **dois portais que leem o mesmo pacote** (decisão do Owner em
14/11/2026). Nenhum dos dois lê o `dbt/target/` nem o *manifest* direto.

---

## 2. Regras de leitura

1. **Por *commit* fixado.** O consumidor registra o *commit* daqui que leu. Os *commits* anteriores
   a `a35a8cb`, o primeiro daqui, existem só no `mvp_eng_dados_1`, que fica como referência histórica.
2. **Publicado antes de anunciado.** Um *commit* só entra na §6 ou num aviso depois de estar no
   `origin/main` do GitHub. O *push* é sempre com a autorização do Owner.
3. **Nenhum consumidor escreve aqui nem roda `make` aqui.** A única exceção é a sessão do `nl_sql`,
   que escreve entradas nos Achados sem *commit*. Ler arquivos e usar `git show`/`git log` neste
   *checkout* é livre. Comandos do projeto não são, nem os que parecem só ler: qualquer
   `dbt … --select` reescreve o `dbt/target/manifest.json`. Para a linhagem e os metadados, a fonte é
   o pacote ou, até ele existir, o esquema e o exemplo.
4. **O que o consumidor exibe tem a data e o *commit* de onde veio.** Uma medição histórica não vira
   número atual por existir.

---

## 3. O banco compartilhado

Os três bancos (`mvp_ed1_source_db`, `mvp_ed1_legacy_db`, `mvp_ed1_warehouse_db`) são **um só
conjunto**, herdado do `mvp_eng_dados_1` com os mesmos volumes e portas. Só este repositório os
opera (`make`). Um consumidor que lê o armazém entra pelo próprio login, hoje só o BI.

**Para ler o banco:**

1. A sessão do consumidor pede ao Owner que os bancos estejam de pé. O Owner sobe com `make up`
   neste repositório, ou pede a esta sessão.
2. **Janela de leitura.** Quando a leitura precisa de um estado estável (exportação, oráculo), o
   consumidor pede uma janela ao Owner. Enquanto ela está aberta, esta sessão não roda `dbt-build`,
   regeneração, restauração nem ingestão. O Owner abre e fecha a janela, e é ele o trinco.
3. **Dentro da janela**, a leitura é do consumidor: uma transação `REPEATABLE READ READ ONLY` dá o
   corte consistente.
4. **Qual *build* está no banco.** Cada *build* que muda o que um consumidor lê entra na §5, com o
   *commit* e o `invocation_id`. E, desde 15/11/2026, o próprio armazém responde
   ([ADR-0054](adr/0054-procedencia-do-armazem-no-log-de-execucao.md)): na mesma transação da leitura,
   `select * from governance.warehouse_provenance` diz `verified`, com o *commit* e a execução, ou
   `not_verified`, com o motivo. Para a leitura sair verificada, **antes de abrir a janela** esta
   sessão roda `make dbt-build` de um *checkout* limpo, sem nada depois dele: execução parcial, da DAG,
   sincronização, restauração ou linha aberta tiram o `verified`. Ele afirma o código da última execução
   integral elegível, não a origem de cada linha retida pela fato incremental e pelos *snapshots*.

---

## 4. Os canais

- **Entrada (puxada).** Cada consumidor escreve as perguntas e os achados no próprio repositório, nos
  arquivos da §1, e esta sessão os lê no início de cada bloco do plano e quando o Owner avisa. Cada
  item recebe uma resposta, aqui ou no plano, pela regra de entrada (plano, Bloco 0, item 3): achado
  novo ganha ID de F14 em diante nos Achados e uma linha no plano, com o bloco de destino.
- **Saída.** Este documento. Quando a mudança é urgente, sai também um aviso fora do Git
  (`data/medicoes/base_consumidores/avisos/`) que aponta para cá. O aviso nunca é a única fonte.

---

## 5. O que mudou para quem consome

As mudanças de **valor**, **esquema** ou **texto** de um objeto que um consumidor lê. Uma linha por
mudança, com o caso de antes e de depois quando é número. O contrato das views pega mudança de
esquema e não pega mudança de valor: por isso a coluna "Caso".

| Estado | Data | *Commit* | Objeto | Muda | Caso: antes → depois | *Build* do armazém | Achado |
|---|---|---|---|---|---|---|---|
| `feita` | 14/11/2026 | `9aeea8d` | `consumption.support_tickets_per_hundred_orders` | **Valor:** o denominador soma as origens do canal pelo nome; 117 linhas no lugar de 118 (a chave mês × canal × categoria deixa de se repetir); 75 taxas mudam | Jan/2024, Conta, Aplicativo: 4,5455 → 4,3478 (22 → 23 pedidos) | `701cc3ea-d3dd-4ccf-8c29-b506c8f7458b` | F1 |
| `feita` | 14/11/2026 | `d212c07` | `analytics.dim_customer` (`order_count`, `first_order_at`) | **Texto:** a descrição diz que a dimensão conta o pedido cujos itens foram todos para a quarentena, que a fato não tem. Nenhum valor muda | 15 clientes do legado, 15 pedidos a mais que a fato | `a1e034c2-5f43-4a08-90fe-9a823a7e1623` | F3 |
| `feita` | 14/11/2026 | `69ea446` | `consumption.inventory_turnover_by_sku_and_warehouse` | **Esquema e valor:** `quantity_on_hand` e `inventory_value_amount` saem; entram `avg_quantity_on_hand` e `avg_inventory_value_amount`, médias do trimestre, ambas `numeric`; o giro passa a ser pelo estoque médio (ADR-0052). Aviso prévio em `3010ead` | 6.990 linhas e o mesmo CMV; 1.449 giros mudam mais de 10%; indefinidos 620 → 1.216 | `1bc2a738-c76b-4435-86e8-6b8e138adb6a` | F2 |
| `feita` | 14/11/2026 | `745fe6a` | `consumption.on_time_delivery_rate_by_carrier` | **Valor:** a view lê `fact_shipment` (nova, uma linha por remessa) e conta também a remessa cujos itens foram todos rejeitados em cascata (ADR-0053, D66). O esquema não muda | Remessas entregues no total: 3.297 → 3.313; 1.175 → 1.180 linhas; 3 taxas mudam | `48462795-d80b-4ecd-837e-361358062d72` | D66 |
| `feita` | 14/11/2026 | `12677a3` | `consumption.order_to_delivery_time_by_region` | **Valor:** a view lê `fact_shipment` e conta também o pedido de itens rejeitados em cascata (F17). O esquema não muda | Pedidos: 2.761 → 2.774 | `66c5bc44-03d1-47e3-acd8-d5e36b5cda5d` | F17 |
| `feita` | 14/11/2026 | `12677a3` | `consumption.new_and_repeat_customers_by_month` | **Valor:** a estreia sai do grão do pedido (`fact_order_status_event`) e conta também o pedido de itens rejeitados (F18). O esquema não muda | Estreias: 1.388 → 1.389; 6 clientes mudam de mês de estreia | `66c5bc44-03d1-47e3-acd8-d5e36b5cda5d` | F18 |
| `feita` | 14/11/2026 | `0471f6a` | `consumption.support_tickets_per_hundred_orders` | **Valor:** o denominador sai do grão do pedido e conta também o pedido de itens rejeitados em cascata (F21). O esquema não muda | 15 combinações de mês e canal com 1 pedido a mais; 4 delas com linha na view | `259d9289-d58d-406a-b2ef-96105a3a174f` | F21 |
| `feita` | 14/11/2026 | `b326c66`, `4e163c9`, `ff3bdfe`, `61e0543` | Descrições de todas as camadas | **Texto** (Bloco 3): o grão das 15 dimensões e a regra de agrupar pelo nome (F8, F12); seis descrições corrigidas (F11, F13 a F16) e as três erradas do F4; a versão curta para o BigQuery (F4); as 141 colunas que não tinham descrição (G06). Nenhum valor nem esquema muda | Colunas sem descrição: 141 → 0 | — | F4, F8, F11 a F16, G06 |
| `feita` | 14/11/2026 | `b22fdcb`, `7ad2943`, `f5b34b5` | `trusted.payments.net_captured_amount`; os textos de recompra pós-pedido, ciclo de entrega e entrega no prazo, nas views e fatos que os citam | **Texto** (revisão do Bloco 3): o saldo do pagamento deixa de dizer que reconcilia com a receita — é valor cobrado, com frete e imposto (RVB3-1-02); as regras que mudam o número passam à versão curta, a que vai ao BigQuery: os dois pedidos realizados e a janela fechada na recompra, a modalidade da remessa que fechou o ciclo, a chegada pelo `delivered` mais recente e a remessa devolvida na pontualidade (RVB3-1-03, RVB3-2-01). Nenhum valor nem esquema muda | — | `0a334682-c957-4327-b863-a46ea14f0e1b` | RVB3-1-02, RVB3-1-03, RVB3-2-01 |
| `feita` | 15/11/2026 | `5fcda58` | `trusted.legacy_order_totals_divergence` | **Esquema:** as quatro colunas em português mudam de nome, sem mudar valor nem tipo: `itens_empilhados` → `accepted_item_count`, `itens_rejeitados` → `rejected_item_count`, `motivos_da_rejeicao` → `rejection_reasons`, `explicada_pela_quarentena` → `explained_by_quarantine` (Q6; CLAUDE.md §2). Nenhuma view lê a relação; o pacote a publica em `relations`. Aviso prévio em `523f661` | — | `9a9ca09e-6286-4de5-99d7-4fe15a86df47` | Q6 |

**A sequência de uma linha.** Mudança de **valor** ou de **texto** entra uma vez só, como `feita`,
depois de *commitada*, publicada e construída no armazém, já com o *commit* e o `invocation_id`.
Mudança de **esquema** entra duas vezes: primeiro como `prevista`, sem *commit* nem *build*, num
*commit* anterior ao que a faz, para o consumidor se preparar; depois, a mesma linha passa a `feita`,
com o *commit* e o `invocation_id`, num *commit* posterior. Nenhuma linha cita o *commit* que a contém.

**O que está previsto mudar de valor, e quando,** está no plano (Blocos 1, 1b e a D66).

**O esquema das views.** O conjunto das 16 views não muda nesta fase, e os Blocos 5 e 6 não mexem em
`consumption`. A `inventory_turnover_by_sku_and_warehouse` mantém o esquema, salvo se a Q8 decidir
outra coisa. A `on_time_delivery_rate_by_carrier` manteve o esquema na D66. Qualquer mudança de esquema entra
aqui como `prevista` antes do *commit* que a faz.

---

## 6. *Commits* marcados para fixar

| Marco | *Commit* | Para quem |
|---|---|---|
| `v2.0.0`, herdada | `f86b9fb`, só no `mvp_eng_dados_1` | Referência histórica |
| Especificação do pacote, formato 1 | Anunciado no aviso que acompanha a publicação (o documento não cita o próprio *commit*) | `gdados` (E1), BI (2.7) |
| Fim da auditoria das 16 views (Bloco 1b, com a P13 depois da D66) | `4da9e60` | BI (N85: as etapas 2.4 a 2.10 fixam este) |
| Primeira versão do pacote (Bloco 4) | `acb26d0` | `gdados`, BI |

---

## 7. O GCP

**Nenhum recurso novo no GCP**, em nenhum projeto (decisão do Owner em 14/11/2026). O ambiente da
Etapa 13 foi destruído em 13/11/2026 e é evidência **datada e congelada**: as declarações
(`terraform/`, o mapa de paridade) e o [Registro da fase GCP](registro_fase_gcp.md) estão aqui; as
evidências coletadas antes do desmonte estão fora do Git, no `mvp_eng_dados_1` (L10, Bloco 4). O custo
real da fase entra em 16/11/2026 no `mvp_eng_dados_1`, como a D92 prevê, e **também aqui**, no mesmo
dia, para que os portais o leiam deste repositório.
