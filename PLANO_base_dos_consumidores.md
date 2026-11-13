# Plano — a base dos consumidores: `gdados`, `nl_sql` e `bi-como-codigo`

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 13/11/2026; rodada 1 respondida no mesmo dia (§6); **aguarda a revisão por outro agente** antes de executar |
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

O `mvp_eng_dados_1` está arquivado (D92): o que eles leem de lá não muda mais, e o que esta fase
corrige aqui **não chega a nenhum deles** até cada um apontar para cá. A mudança é de cada
consumidor, na sessão dele; aqui só se decide o que este repositório oferece (Q1).

---

## 2. O inventário, por consumidor

Cada linha aponta para o dono do conteúdo. **G** = `gdados`, **N** = `nl_sql` (achado que volta),
**B** = `bi-como-codigo`.

| # | Item | Dono do conteúdo | Serve a | Pede decisão? |
|---|---|---|---|---|
| 1 | F1 — `support_tickets_per_hundred_orders` perde parte do denominador (73 de 117 taxas, pelo nome do canal) | Achados §1 | B (número errado na vitrine), G, N | Não: correção de defeito |
| 2 | F2 — `inventory_turnover_by_sku_and_warehouse` usa o saldo corrente, não o médio do trimestre | Achados §1 | B, G, N | **Sim, Q2** — regra de valorização |
| 3 | F3 — `dim_customer` e `fact_sales_order_item` discordam em 15 clientes `legacy` | Achados §1 | G, N | Depois da causa: se a causa for regra, sim |
| 4 | F4 — três descrições erradas e quatro cortadas pelo limite de 1.024 do BigQuery | Achados §1 | G, N | Não |
| 5 | F5 — o glossário de receita líquida, ticket médio e lucro bruto omite `is_realised` | Achados §1 | G, N, B | Não |
| 6 | F6 — sete FKs sem teste `relationships` (0 órfãos medidos lá) | Achados §1 | G, N | Não |
| 7 | F7 — domínios categóricos sem lista nem significado (42 domínios, 80 colunas, lá) | Achados §1 | G, N | **Sim, Q3** — formato; `meta` novo pode pedir ADR |
| 8 | F8 — grão declarado em 10 das 25 tabelas de `analytics` | Achados §1 | G, N | Não |
| 9 | F9 — regras de negócio que só existem no SQL de `consumption` | Achados §1 | G, N, B | **Sim, Q3** — formato; camada semântica pede ADR |
| 10 | F10 — PK/FK só como teste, sem *constraint* declarada | Achados §1 | G, N | **Sim, Q4** — mudança de modelagem, ADR |
| 11 | G06 — 141 colunas declaradas sem descrição (5 `staging`, 125 `trusted`, 5 `quarantine`, 6 `snapshots`) | V2; `PLANO_revisao_governanca.md` §4 e RVG-1-01 a 03 | G | Uma: Q6 (nomes em português), rodada 2 |
| 12 | D91 — o pacote de metadados para o portal | D91; `PLANO_revisao_governanca.md` §5 e RVG-1-04 | G (e B, se quiser a mesma fonte) | Decidida; falta o contrato da guarda, na implementação |
| 13 | V1 — itens 4 a 9 dos lotes 2 e 3 (guarda de identidade sintática, formas que o escritor e a guarda do fuso não leem) | V1 | B (a guarda protege o que ele lê) | Não nesta fase: a V1 manda voltar a cada grupo antes de mexer no código dele |

Fora desta fase, por não servir aos consumidores: o `airbyte_internal` da V2 (só existia no GCP),
a V3 inteira (o item 9, o custo, tem data própria: 16/11), D43, D63, D64 e D66.

---

## 3. Blocos, na ordem proposta

A regra da ordem: **primeiro o que torna errado um número ou um texto que um consumidor já lê**;
depois o que é texto e teste sem decisão; o pacote do portal quando houver conteúdo para levar; por
último o que pede ADR.

### Bloco 0 — a fronteira com os consumidores (só documentos)

1. O Owner revisa `docs/achados_nl_sql.md` e a linha do README (escritos pela sessão do `nl_sql`,
   que não *commita* aqui sem pedido); *commit* próprio.
2. Registrar aqui a resposta da Q1: de onde cada consumidor lê. Não editar os outros repositórios:
   cada um muda na sessão dele, e este bloco entrega o texto do aviso para cada sessão.

### Bloco 1 — os números (F1, F3, F2)

- **F1:** reescrever a view para agregar chamados e pedidos cada um no grão final (mês × canal pelo
  nome × categoria) e só então dividir. Teste novo que reproduz o caso de jan/2024 (Conta,
  Aplicativo: 4,35, e não 4,55) e um teste de reconciliação do denominador contra a fato.
  Efeito no `bi-como-codigo`: o esquema da view não muda, os valores mudam — o oráculo do
  custodiante (M2 lá) precisa ser refeito na sessão dele.
- **F3:** diagnóstico primeiro, sem mudar nada: achar por que 15 clientes `legacy` têm 38 pedidos na
  dimensão e 23 na fato (quarentena? itens ausentes? fuso na primeira compra?). Com a causa medida,
  ou reconciliar, ou documentar o recorte de cada fonte — se a causa for regra, vira pergunta.
  Em qualquer caso, um teste de reconciliação dimensão × fato com a exceção declarada.
- **F2:** pela resposta da Q2.

### Bloco 2 — os testes que faltam (F6)

Os sete `relationships` em `_analytics__models.yml`. Sem decisão: é a mesma regra das outras 46 FKs.

### Bloco 3 — o texto (F5, F4, F8, G06)

- **F5:** a regra do pedido realizado no glossário (receita líquida, ticket médio, lucro bruto) e na
  descrição de `net_revenue_amount`.
- **F4:** as três descrições erradas; as quatro longas ganham uma versão curta e completa
  (≤ 1.024 caracteres), e a macro `descricao_no_bigquery` passa a **recusar** em vez de cortar — a
  falha aparece no `make check`, não no catálogo do BigQuery. A recusa precisa de uma forma de
  declarar a versão curta; o desenho vai à revisão junto com o do RVG-1-01.
- **F8:** "**Grão:**" nas 15 dimensões.
- **G06:** o Bloco B do `PLANO_revisao_governanca.md`, na ordem que o RVG-1-02 corrigiu, com o
  desenho do RVG-1-01 revisado antes e os *snapshots* pelo RVG-1-03. A catraca baixa no mesmo
  *commit* de cada melhora.

### Bloco 4 — o pacote do portal (D91)

A implementação da D91, com o contrato da guarda do RVG-1-04 e as contraprovas que ele pede (clone
sem artefatos, regeneração repetida, *commit* posterior sem mudança dos insumos). Entra **depois**
dos Blocos 1 a 3 para que a primeira versão do pacote já leve o texto corrigido, mas **antes** dos
Blocos 5 e 6, para que o `gdados` possa abrir a E1 sem esperar os ADRs. O formato acompanha versão
(como o `lineage --json`); o que os Blocos 5 e 6 acrescentarem entra como campo novo, sem quebrar.

### Bloco 5 — domínios e métricas (F7, F9)

Pela resposta da Q3. Em qualquer formato, cada valor e cada métrica é conferido contra o dado ou
contra a view por teste — a verificação do `nl_sql` (23 de 23 gabaritos reproduzidos só a partir
das definições) é o modelo, e aqui a referência seria a view de `consumption`.

### Bloco 6 — as chaves declaradas (F10)

Pela resposta da Q4.

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
| R11: `make check` e `dbt build` no armazém local | `make preflight ALVO=check` antes, sem `FORCE` |
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

## 7. Definição de pronto aplicada

A do [`CLAUDE.md` §7](CLAUDE.md#7-definição-de-pronto), por bloco. O que muda nesta fase:

- cada número corrigido tem o caso de antes e de depois medido no armazém local, e um teste que o
  guarda;
- cada bloco atualiza a entrada correspondente dos Achados do nl_sql ("replicado aqui em `<commit>`")
  e a V2;
- o pacote da D91 regenerado e em dia em cada *commit* depois do Bloco 4.

## 8. Ordem

1. Rodada 1 (§6). Revisão deste plano por outro agente.
2. Bloco 0.
3. Blocos 1, 2 e 3, cada um revisado antes do seguinte.
4. Bloco 4.
5. Rodada 2; Blocos 5 e 6, com os ADRs.
6. Fechamento.

**Estimativa:** não há. O G06 sozinho foi estimado em 2 a 3 h de escrita mais a revisão do Owner
(planejado, não medido); os outros blocos não foram estimados.
