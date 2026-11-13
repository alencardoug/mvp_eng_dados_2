# Plano — a base dos consumidores: `gdados`, `nl_sql` e `bi-como-codigo`

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 13/11/2026; rodada 1 de perguntas respondida no mesmo dia (§6); revisão do Codex, rodadas 1 e 2, respondidas (§9); **aguarda a rodada 3 da revisão** antes de executar |
| Origem | Pedido do Owner, 13/11/2026: "a próxima fase é favorecer e completar o trabalho que dá base para `gdados`, `nl_sql` e `bi-como-codigo`" |
| Base | `5df9536` (`origin/main`), com `README.md` e `docs/achados_nl_sql.md` alterados e fora do Git |
| Sai do repositório | Com `git rm`, quando a fase fechar; o que ficar aberto vai para as [Pendências](docs/pendencias.md) |

Este plano **não decide nada**: ordena o que já está aberto em outros donos — a V2 e a D91 das
[Pendências](docs/pendencias.md), o Bloco B do `PLANO_revisao_governanca.md` e as falhas F1 a F10
dos [Achados do nl_sql](docs/achados_nl_sql.md) — pelo que cada consumidor precisa, e lista as
decisões que faltam. O conteúdo de cada item continua no dono dele; aqui só a ordem, a dependência
e a pergunta.

---

## 1. O que cada consumidor lê daqui

| Consumidor | O que lê | Como, hoje | Onde está o contrato |
|---|---|---|---|
| **`gdados`** (portal, não começou: D01–D03 pendentes lá) | Descrições, sensibilidade, `meta`, linhagem, glossário, travessias, faltas da catraca, procedência | Ainda nada; a D91 decidiu um pacote JSON versionado **aqui**, regenerado no `make catalog` | D91 (Pendências §2); E1 do `PLANO.md` do `gdados` |
| **`nl_sql`** (banco de provas NL→SQL, privado) | Nada mais: importação **única e congelada** de 11–12/11/2026 (`cbc5271`) | O caminho é o inverso: ele devolve achados por `docs/achados_nl_sql.md` | `docs/achados_nl_sql.md` |
| **`bi-como-codigo`** (vitrine, Parte II em andamento) | As 16 views por um login de `analyst`; o esquema e a versão de cada view, fixados lá; `lineage --json`; trechos de SQL e documentos por *commit* fixado | `ENG_DADOS_DIR` aponta para um *checkout*; o padrão é `~/Projetos/mvp_eng_dados_1` | §3.5 do `PLAN.md` do `bi-como-codigo` |

**O que o `nl_sql` mostra serve aos outros dois.** Ele mediu o que acontece quando uma ferramenta
lê só a governança: o glossário sem a regra do pedido realizado (F5), as descrições cortadas (F4), os
domínios sem significado (F7), as regras que só existem no SQL (F9). O portal do `gdados` exibe essa
mesma governança para uma pessoa, e a vitrine do `bi-como-codigo` mostra os números de uma das views
com defeito (F1). Corrigir aqui é a base comum.

### 1.1 O ponto transversal: os três apontam para o `mvp_eng_dados_1`

Conferido em 13/11/2026, só por leitura:

- `gdados/README.md`: "Fonte consultada nesta avaliação: `../mvp_eng_dados_1`".
- `bi-como-codigo`: `Makefile` (`docs-check`, `check` exige `ENG_DADOS_DIR` de um *checkout* do
  `mvp_eng_dados_1`), os *scripts* de `evidence/` com o mesmo padrão, e os links fixados em
  *commits* do `mvp_eng_dados_1`.
- `nl_sql/CLAUDE.md`, regra 1: o canal de volta em `~/Projetos/mvp_eng_dados_1/docs/achados_nl_sql.md`,
  arquivo que foi **movido** para cá em 13/11. O caminho de lá está errado desde então.

O `mvp_eng_dados_1` está arquivado (D92), mas apontar para lá separa três coisas que não andam
juntas (RVC-1-05):

- **o banco é o mesmo.** A D92 herdou contêineres, volumes e portas, e o leitor do `bi-como-codigo`
  (`evidence/20261022/ro.sh`) entra no `mvp_ed1_warehouse_db` qualquer que seja o *checkout*. Uma
  reconstrução feita aqui muda o **próximo** resultado que o BI ler, antes de ele trocar o
  `ENG_DADOS_DIR`; o que já foi exportado não muda sozinho;
- **os artefatos novos** — SQL, `.yml`, glossário, o `lineage --json`, o pacote da D91 — só chegam a
  quem fixar um *commit* daqui;
- **as referências históricas** não se resolvem aqui: este repositório nasceu sem histórico (D92), e
  `git show 26b58b3:…` falha nele. Os links e *commits* do `mvp_eng_dados_1` continuam pedindo um
  *checkout* dele.

A mudança é de cada consumidor, na sessão dele; aqui só se decide o que este repositório oferece (Q1).

---

## 2. O inventário, por consumidor

Cada linha aponta para o dono do conteúdo. **G** = `gdados`, **N** = `nl_sql` (achado que volta),
**B** = `bi-como-codigo`.

| # | Item | Dono do conteúdo | Serve a | Pede decisão? |
|---|---|---|---|---|
| 1 | F1 — o denominador de `support_tickets_per_hundred_orders` | Achados §1 | B (número na vitrine), G, N | Não: correção de defeito |
| 2 | F2 — o estoque do denominador de `inventory_turnover_by_sku_and_warehouse` | Achados §1 | B, G, N | **Sim, Q2** (respondida) e **Q8** — a regra completa do cálculo, antes do SQL |
| 3 | F3 — a população de `dim_customer` contra a de `fact_sales_order_item` | Achados §1 | G, N | Depois da causa: se a causa for regra, sim |
| 4 | F4 — descrições erradas e cortadas pelo limite do BigQuery | Achados §1 | G, N | Não |
| 5 | F5 — o glossário de receita sem a regra do pedido realizado | Achados §1 | G, N, B | Não |
| 6 | F6 — as FKs sem teste `relationships` | Achados §1 | G, N | Não |
| 7 | F7 — domínios categóricos sem lista nem significado | Achados §1 | G, N | **Sim, Q3** (respondida) — formato, com ADR |
| 8 | F8 — o grão das dimensões | Achados §1 | G, N | Não |
| 9 | F9 — regras de negócio que só existem no SQL de `consumption` | Achados §1 | G, N, B | **Sim, Q3** (respondida) — formato, com ADR |
| 10 | F10 — PK/FK só como teste | Achados §1 | G, N | **Sim, Q4** (respondida) — ADR, com o ciclo da RVC-1-01 |
| 11 | G06 — as colunas declaradas sem descrição | V2; `PLANO_revisao_governanca.md` §4 e RVG-1-01 a 03 | G | Uma: Q6, rodada 2 |
| 12 | D91 — o pacote de metadados para o portal | D91; `PLANO_revisao_governanca.md` §5 e RVG-1-04 | G (e B, se quiser a mesma fonte) | Decidida; falta o contrato da guarda, na implementação |
| 13 | V1 — os itens dos lotes 2 e 3 | V1 | B (a guarda protege o que ele lê) | Não: a V1 manda **voltar ao grupo antes de mexer no código dele** — passo explícito nos Blocos 3 a 5 (RVC-1-06) |

Fora desta fase: o `airbyte_internal` da V2 (só existia no GCP), a V3 inteira (o item 9, o custo,
tem data própria: 16/11), D43, D63 e D64, por não servirem aos consumidores. A **D66** serve a eles —
ela recorta a população da P13, que o portal precisa exibir (G08) e a vitrine mostra —, mas fica fora
por ser decisão de modelagem adiada; a limitação dela vai no aviso do Bloco 0 e no pacote, e o
fechamento desta fase não declara os consumidores livres dela (RVC-1-09).

---

## 3. Blocos, na ordem proposta

A regra da ordem: **primeiro o que torna errado um número ou um texto que um consumidor já lê**;
depois o que é texto e teste sem decisão; o pacote do portal quando houver conteúdo para levar; por
último o que pede ADR.

### Bloco 0 — a fronteira com os consumidores (só documentos)

1. O Owner revisa `docs/achados_nl_sql.md` e a linha do README (escritos pela sessão do `nl_sql`,
   que não *commita* aqui sem pedido); *commit* próprio.
2. Registrar aqui a resposta da Q1: de onde cada consumidor lê. Não editar os outros repositórios:
   cada um muda na sessão dele, e este bloco entrega o texto do aviso para cada sessão. O aviso
   separa as três coisas do §1.1 — a leitura do banco, que já é a daqui; os artefatos novos, por
   *commit* fixado daqui; e as referências históricas, que seguem pedindo um *checkout* do
   `mvp_eng_dados_1` — e diz quais views mudam de valor e quando (RVC-1-05). Para o `nl_sql`, só o
   canal de volta muda: a regra 2 do `CLAUDE.md` de lá proíbe reimportar.

### Bloco 1 — os números (F1, F3, F2)

- **F1:** dois grãos, cada um agregado no seu antes de dividir (RVC-1-03). O **numerador** por mês ×
  canal pelo nome × categoria; o **denominador** por mês × canal pelo nome, **sem categoria** — "o
  denominador é do canal, não da categoria" (`support_tickets_per_hundred_orders.sql:12–17`) —,
  somando todas as origens, e repetido em cada linha de categoria do numerador, sem depender de
  quais origens ou categorias tiveram chamado. Ficam como estão: o esquema, `channel_type` e o grupo
  da categoria, a saída esparsa e a taxa nula de "Sem canal"; a média de horas até a resolução sai
  dos eventos, nunca média de médias por origem. Teste com a precisão vigente, de quatro casas: o
  caso de jan/2024 (Conta, Aplicativo) dá **4,3478** (100/23), e não 4,5455 (100/22) — o 4,35 dos
  Achados é a apresentação em duas casas. O teste guarda também origem sem chamado, várias categorias
  e "Sem canal". A reconciliação fato × consumo leva a *tag* `fronteira`, para rodar depois da view
  na DAG (`airflow/dags/fluxo_batch.py`), e não repetir o M45 do `bi-como-codigo`. Efeito lá: o
  esquema não muda, os valores mudam — o oráculo do custodiante (M2) é refeito na sessão dele.
- **F3:** diagnóstico primeiro, sem mudar nada: achar por que a dimensão e a fato divergem nos
  clientes `legacy` (Achados, F3). A cadeia a medir: `trusted/customers.sql` conta pedidos realizados;
  `trusted/orders.sql` conserva pedido sem item; a fato parte dos itens; a D35 preserva o pai quando o
  filho é rejeitado. A comparação reduz as versões SCD e separa pedido aceito de pedido com item
  aceito; o fuso da primeira compra também entra. Com a causa medida,
  ou reconciliar, ou documentar o recorte de cada fonte — se a causa for regra, vira pergunta.
  Em qualquer caso, um teste de reconciliação dimensão × fato com a exceção declarada.
- **F2:** pela Q2-a, em quatro passos (RVC-1-02, rodadas 1 e 2). O F1 e o F3 não esperam por ele.
  1. **Diagnóstico, sem mudar nada:** a diferença entre o saldo e a soma dos movimentos, por origem,
     par SKU × armazém e captura, separando o tempo de evento (`occurred_at`) do recorte de ingestão
     (`recorded_at <= ingested_at`, de `trusted.inventory_balances`). O estoque de abertura já é um
     movimento (`adjustment_in` em `motor.inicio`, `generator/domains/estoque.py`) e não se soma de
     novo. Os movimentos rejeitados do legado ficam em `quarantine` e não voltam; a diferença que eles
     explicam está na regra `explicado_pela_quarentena`.
  2. **A proposta da regra, escrita e com o diagnóstico ao lado:** a média no tempo (diária? ponderada
     pelo tempo entre eventos?), os limites do trimestre no fuso, o período sem movimento, o evento
     atrasado, a valorização — hoje `avg(unit_cost)` de **todos** os movimentos, inclusive os
     posteriores; o ADR-0030 define o CMV da saída, não o valor do estoque médio — e o histórico
     incompleto, sem abertura residual silenciosa. A proposta separa o que já decorre de regra vigente
     do que é escolha nova.
  3. **A decisão do Owner, a Q8**, sobre a proposta: as escolhas novas e se a regra pede ADR. O F2
     para aqui até a resposta.
  4. **O SQL e as provas:** movimento e custo posteriores não mudam trimestre fechado; evento atrasado;
     par legado incompleto. A regra aprovada vive no dono dela — o glossário (`giro_de_estoque.md`) e o
     ADR, se houver —, e o plano só aponta para lá.

### Bloco 2 — os testes que faltam (F6)

Os sete `relationships` em `_analytics__models.yml`, de 44 para 51. Sem decisão: é a mesma regra das
outras. Os órfãos são medidos aqui antes, no armazém local.

### Bloco 3 — o texto (F5, F4, F8, G06)

- **F5:** a regra do pedido realizado no glossário (receita líquida, ticket médio, lucro bruto) e na
  descrição de `net_revenue_amount`.
- **F4:** as três descrições erradas, e **todas** as que passam de 1.024 caracteres — o *manifest* de
  13/11 tem oito, quatro em `analytics` e quatro em `consumption`, não só as quatro que o `nl_sql`
  viu (RVC-1-04). Cada uma ganha uma versão curta e completa. A macro `bigquery__alter_column_comment`
  só roda no BigQuery, e o `make check` não a alcança: a guarda é **um teste local sobre o
  *manifest***, que mede o texto destinado ao BigQuery e recusa acima do limite, com contraprova. A
  macro pode recusar também, mas não é ela a prova. Onde a versão curta vive e como ela herda vão ao
  desenho junto com o do RVG-1-01. A aplicação real no BigQuery fica não medida.
- **F8:** "**Grão:**" nas 15 dimensões.
- **G06:** o Bloco B do `PLANO_revisao_governanca.md`, na ordem que o RVG-1-02 corrigiu, com o
  desenho do RVG-1-01 revisado antes e os *snapshots* pelo RVG-1-03. A catraca baixa no mesmo
  *commit* de cada melhora.
- **Antes do F4 e do G06, a volta ao lote 3 da V1** (RVC-1-06): os dois mexem em
  `src/mvp_ed1/models/` (o contrato de descrição da ponte, `descriptions.py:295–303`). Cada item
  aplicável — 6 a 9 — sai com um resultado escrito: exercitado, limite preservado ou continua aberto.
  Não promete fechar a V1 inteira.

### Bloco 4 — o pacote do portal (D91)

A implementação da D91, com o contrato da guarda do RVG-1-04 e as contraprovas que ele pede (clone
sem artefatos, regeneração repetida, *commit* posterior sem mudança dos insumos), e antes dela a volta
ao item 9 da V1 — a conferência de *manifest* atrasado, de que a guarda depende (RVC-1-06). Entra **depois**
dos Blocos 1 a 3 para que a primeira versão do pacote já leve o texto corrigido, mas **antes** dos
Blocos 5 e 6, para que o `gdados` possa abrir a E1 sem esperar os ADRs. O formato acompanha versão
(como o `lineage --json`); o que os Blocos 5 e 6 acrescentarem entra como campo novo, sem quebrar.

### Bloco 5 — domínios e métricas (F7, F9)

Pela Q3-a. O ADR do formato preserva as chaves de `meta` que já existem (`sensitivity`,
`description_from`, `description_inherited`, `description_reason`); o significado nasce no `.yml`
declarativo, nunca no `_derived.yml`. Em qualquer formato, cada valor e cada métrica é conferido contra o dado ou
contra a view por teste — a verificação do `nl_sql` (23 de 23 gabaritos reproduzidos só a partir
das definições) é o modelo, e aqui a referência seria a view de `consumption`.

### Bloco 6 — as chaves declaradas (F10)

Pela Q4-a. O ADR declara **o ciclo de vida das *constraints***, sem o qual elas se perdem em silêncio
(RVC-1-01):

- o dbt recria cada tabela de `analytics` por troca de nomes e apaga a antiga com `drop … cascade`:
  a FK de uma fato para uma dimensão recriada cai junto e não volta a apontar para a nova;
- a `fact_inventory_movement` é incremental (`merge` no ramo `retail`, exclusão prévia do ramo
  `legacy`): ela não é recriada e não reinstala as FKs que perdeu; e o *contract* numa tabela que já
  existe pede migração explícita;
- o *contract* exige `data_type` nas 477 colunas de `analytics`, hoje sem nenhum, nos dois adaptadores.

O desenho cobre instalação inicial, dependência, substituição, reposição e recuperação depois de
falha, e preserva o `make dbt-build RESET=1` (*snapshots* e `--full-refresh` juntos, porque a chave das
SCD tipo 2 leva o `dbt_valid_from`). A prova lê as *constraints* no catálogo do PostgreSQL depois da
carga inicial, de uma segunda execução incremental, de uma reconstrução só de dimensão e do
`RESET=1`, e lê o `consumption` no fim. O `relationships` continua: ele prova os valores, não a
existência da *constraint*. No BigQuery elas são `NOT ENFORCED`, e a prova local não vale como DDL
executado lá. Se o desenho mudar a materialização, ele volta ao Owner antes de implementar.

### Fechamento

`make check` verde; catálogo, dicionário, linhagem e pacote regenerados; revisão por outro agente
por bloco; a nota de versão. A *tag* — a primeira deste repositório — é pergunta da rodada 2.

---

## 4. O que já foi conferido para escrever este plano (sem efeito)

Em 13/11/2026, só leitura de arquivo:

- F1: `dbt/models/consumption/support_tickets_per_hundred_orders.sql:119–124` parte de
  `chamados_por_mes` e junta `pedidos_por_mes` por `sales_channel_key`, como o achado diz.
- F2: `inventory_turnover_by_sku_and_warehouse.sql:54–58` multiplica `quantity_on_hand` de
  `inventory_balances` pelo custo médio, como o achado diz.
- F4: `dbt/macros/descricao_no_bigquery.sql` corta em 1.024 com o aviso "texto completo no catálogo".
- F5: `docs/glossario_de_negocio/receita_liquida.md` não menciona `is_realised` nem "realizado".
- G06: os tetos de `tests/test_descricao.py` somam 141 (5 + 125 + 5 + 6), como a V2 diz.
- Os apontamentos para o `mvp_eng_dados_1` nos três consumidores (§1.1).

**Não conferido:** os números do `nl_sql` (73 de 117 taxas, 15 clientes, 0 órfãos nas 7 FKs, os 42
domínios) foram medidos lá, no BigQuery de 11/11, e **não aqui**. Cada bloco os mede de novo no
armazém local antes de corrigir (P5); a importação do `nl_sql` é anterior a nada que tenha mudado
os dados, mas isso também se confere.

## 5. Riscos

| Risco | Tratamento |
|---|---|
| R14: volume de texto e teste que ninguém revisa (G06 sozinho são ~140 textos) | *Commits* por domínio; revisão integral do declarativo, amostragem do derivado |
| R11: `make check` e `dbt build` no armazém local | `make preflight ALVO=trabalho` antes (nada em andamento), sem `FORCE`; o `ALVO=check` desta linha na rodada 1 não existe |
| Mudar um número que a vitrine já mostra sem avisar | O contrato do `bi-como-codigo` falha pelo esquema, não pelo valor: o aviso do Bloco 0 diz quais views mudam de valor |
| Inventar significado de valor ou métrica (P5) | Texto lido do SQL ou do dado; o duvidoso vira pergunta |
| Copiar o desvio do `nl_sql` como se fosse correção | Achados §3: só as 25 tabelas, P11 fora, governança em inglês — não se copiam |
| O pacote nascer antes do texto e ser lido como completo | As faltas da catraca vão explícitas no pacote (D91) |

## 6. Decisões pedidas ao Owner

### Rodada 1 — respondida em 13/11/2026

| | Decisão do Owner |
|---|---|
| **Q1** | **(a)** Os consumidores leem **daqui**, por *commit* fixado; o `mvp_eng_dados_1` fica como referência histórica da `v2.0.0`. A mudança é de cada consumidor, na sessão dele; o Bloco 0 escreve o aviso |
| **Q2** | **(a)** O giro passa a usar o **estoque médio do período**, reconstruído de saldo inicial e movimentos |
| **Q3** | **(a)** **Declarativo no dbt**: `accepted_values` com o significado em `meta` da coluna; métricas estruturadas no glossário, com teste contra a view; **ADR curto** do formato, no Bloco 5 |
| **Q4** | **(a)** ***Contract* e *constraints*** nos modelos de `analytics`, com **ADR**, no Bloco 6 |

As opções como foram apresentadas:

| | Pergunta | Recomendação | Alternativas |
|---|---|---|---|
| **Q1** | De onde os consumidores leem | **(a)** daqui, do `mvp_eng_dados_2`, por *commit* fixado, como já fazem; o `mvp_eng_dados_1` vira só referência histórica (`v2.0.0`) | (b) continuam no `mvp_eng_dados_1` até a primeira *tag* daqui; (c) cada consumidor decide na sessão dele |
| **Q2** | F2, o giro de estoque | **(a)** estoque médio do período, reconstruído de saldo inicial e movimentos — a métrica passa a medir o que o nome e o glossário dizem | (b) renomear para "CMV do trimestre ÷ saldo corrente valorizado"; (c) adiar e marcar a view como limitação conhecida |
| **Q3** | F7 e F9, o formato dos domínios e das métricas | **(a)** declarativo no dbt: `accepted_values` com o significado em `meta` da coluna, e as métricas estruturadas no glossário (fórmula, numerador, denominador, filtro, data, grão) com teste contra a view; ADR curto do formato | (b) camada semântica do dbt (*metrics*/MetricFlow) — componente novo, ADR com custo e contrapartida no GCP; (c) arquivos canônicos à parte, como o `nl_sql` |
| **Q4** | F10, as chaves | **(a)** *contract* e *constraints* nos modelos de `analytics` (PK e FK declaradas; no PostgreSQL, impostas), com ADR | (b) só declaradas nos metadados e no pacote, sem *constraint* no banco; (c) adiar até a fase GCP ser reaberta, onde o efeito (Gemini, Knowledge Catalog) aparece |

### Rodada 2 — depois da revisão do plano

| | Pergunta |
|---|---|
| **Q5** | A primeira *tag* deste repositório: o nome (`v2.1.0`, `v3.0.0`) e o que ela fecha |
| **Q6** | A O1 do `PLANO_revisao_governanca.md`: renomear para inglês as três colunas de `trusted.legacy_order_totals_divergence`, ou registrar como exceção |
| **Q7** | O F3, se a causa medida for regra |
| **Q8** | O F2, sobre a proposta do passo 2: a média no tempo, a valorização do estoque médio, os cortes do trimestre e o fuso, o evento atrasado, o par cujo histórico não reconstrói o saldo (legado com movimento rejeitado) — e se a regra pede ADR. Perguntada **no Bloco 1**, logo depois do diagnóstico, e não com as outras (RVC-1-02) |

## 7. Definição de pronto aplicada

A do [`CLAUDE.md` §7](CLAUDE.md#7-definição-de-pronto), por bloco. O que muda nesta fase:

- cada número corrigido tem o caso de antes e de depois medido no armazém local, e um teste que o
  guarda;
- cada bloco atualiza a entrada correspondente dos Achados do nl_sql ("replicado aqui em `<commit>`")
  e a V2;
- o pacote da D91 regenerado e em dia em cada *commit* depois do Bloco 4.

## 8. Ordem

1. ~~Rodada 1 (§6). Revisão deste plano por outro agente~~ (rodadas 1 e 2, §9). Rodada 3 da revisão, sobre a resposta ao RVC-1-02.
2. Bloco 0.
3. Blocos 1, 2 e 3, cada um revisado antes do seguinte. No Bloco 1, o F2 para depois do diagnóstico
   e da proposta, até a **Q8**; o F1 e o F3 seguem.
4. Bloco 4.
5. Rodada 2 de perguntas (Q5 a Q7); Blocos 5 e 6, com os ADRs.
6. Fechamento.

**Estimativa:** não há. O G06 sozinho foi estimado em 2 a 3 h de escrita mais a revisão do Owner
(planejado, não medido); os outros blocos não foram estimados.

---

## 9. Rodadas de revisão

### Rodada 1 — Codex conta 1, sobre o plano em `953f9e1` (13/11/2026, 04:52)

`gpt-6-astra`, esforço *high*, só leitura. Veredito: **mudanças necessárias** — três bloqueantes, quatro
ajustes e duas observações; as decisões Q1 a Q4 ficam. Relatório, pedido e *log* fora do Git, em
`data/medicoes/base_consumidores/` (`codex1_plano_r1*`). Cada achado foi reproduzido no código antes
da resposta.

| # | Onde | Achado | Veredito | Situação |
|---|---|---|---|---|
| RVC-1-01 | Bloco 6 / Q4-a | Falta instalar e manter PK/FK quando o dbt recria as dimensões e preserva a fato incremental; tipos e provas do ciclo não planejados | bloqueante | **Aceito.** Reproduzido: `default__drop_table` é `drop table if exists … cascade`; `analytics` é `table`, com a `fact_inventory_movement` incremental (`merge` + exclusão do `legacy`). O Bloco 6 passou a exigir o ciclo de vida no ADR, `data_type` nas colunas e a prova física nas quatro situações |
| RVC-1-02 | Bloco 1 / F2 / Q2-a | Reconstrução e valorização não tratam o livro legado incompleto, a abertura e os cortes no tempo | bloqueante | **Aceito.** Reproduzido: a ponte só leva `accepted`/`corrected`; `inventory_balances` corta por `recorded_at <= ingested_at`; a view usa `avg(m.unit_cost)` de todos os movimentos. O F2 virou diagnóstico e depois regra especificada; o tratamento do histórico incompleto e o ADR viraram a **Q8** |
| RVC-1-03 | Bloco 1 / F1 | O denominador recebeu uma categoria que pedido não tem; o caso de teste confunde duas e quatro casas | bloqueante | **Aceito.** Reproduzido: `support_tickets_per_hundred_orders.sql:12–17` ("o denominador é do canal"); `round(100/23, 4)` = 4,3478, `round(100/22, 4)` = 4,5455. O F1 tem agora os dois grãos, o que se preserva, os casos do teste e a *tag* `fronteira` |
| RVC-1-04 | Bloco 3 / F4 | A recusa na macro do BigQuery não chega ao `make check`; há mais quatro descrições longas em `consumption` | ajuste | **Aceito.** Reproduzido: as oito descrições acima de 1.024 no *manifest* de 13/11 07:33Z. O F4 cobre as oito, e a guarda é um teste local sobre o *manifest* |
| RVC-1-05 | §1.1 e Bloco 0 / Q1-a | A transição não separa o banco compartilhado, os artefatos novos e os *commits* históricos | ajuste | **Aceito.** Reproduzido: `git show 26b58b3:docs/governanca_de_dados.md` falha aqui; o `ro.sh` do BI entra no `mvp_ed1_warehouse_db`. A frase "não chega a nenhum deles" saiu; o §1.1 e o aviso do Bloco 0 separam as três coisas |
| RVC-1-06 | V1 e Blocos 3 a 5 | Falta voltar ao grupo da V1 antes de mexer na maquinaria de metadados e na guarda dela | ajuste | **Aceito.** A volta aos itens 6 a 9 entra como passo antes do F4 e do G06, e ao item 9 antes da D91, cada item com resultado escrito |
| RVC-1-07 | §2 | O inventário duplica medições dos donos | ajuste | **Aceito.** A tabela do §2 ficou com ID, dono, consumidor e decisão, sem contagem; os números do F3 saíram do Bloco 1. O §4 mantém só a lista do que não foi medido aqui (P5) |
| RVC-1-08 | Bloco 2 | São 44 `relationships`, não 46 | observação | **Aceito.** Reproduzido: 44 ocorrências de `- relationships:` em `953f9e1`; o meu 46 contou outras ocorrências da palavra. Bloco 2: de 44 para 51 |
| RVC-1-09 | §2, exclusões | A D66 serve aos consumidores; o adiamento não pode ser justificado por irrelevância | observação | **Aceito.** A exclusão agora diz o motivo certo (decisão adiada), e a limitação vai no aviso e no pacote |

**Achados próprios, na resposta:**

- o `make preflight ALVO=check` do §5 não existe (`preflight: alvo desconhecido 'check'`); o alvo é
  `ALVO=trabalho`. Corrigido;
- o dossiê (`REVISAO.md` §6) dizia que o `catalog.json` tinha sido regerado pelo `make check` e dava
  ~04:47 como hora do *manifest*: o `catalog.json` não existe, e o *manifest* é de 07:33Z (04:33).
  Corrigido no dossiê.

### Rodada 2 — Codex conta 2, sobre `fc04cd9` (13/11/2026, 05:07)

`gpt-6.1-sol`, esforço *high*, só leitura; a conta 1 bateu no limite de uso no começo da rodada e não
gravou relatório. Veredito: **mudanças necessárias** — RVC-1-01 e RVC-1-03 a 09 **resolvidos**, nenhum
achado novo; o RVC-1-02 **parcial**. Relatório, pedido e *log* em `data/medicoes/base_consumidores/`
(`codex2_plano_r2*`).

| # | Onde | Achado | Veredito | Situação |
|---|---|---|---|---|
| RVC-1-02 | Bloco 1 / F2; Q8; §8 | A aprovação da regra completa (média no tempo, valorização, cortes, atraso) não ia ao Owner; a Q8 ficava depois dos blocos que dependem dela | bloqueante | **Aceito.** Reproduzido: o glossário (`giro_de_estoque.md`) diz "média do período" sem o cálculo; o §8 punha a rodada 2 de perguntas depois do Bloco 4. O F2 tem agora quatro passos — diagnóstico, proposta, Q8, SQL —; a Q8 cobre a regra inteira e é perguntada no Bloco 1; o §8 diz que o F2 para ali e o F1 e o F3 seguem |

