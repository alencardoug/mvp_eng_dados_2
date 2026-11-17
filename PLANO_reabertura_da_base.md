# Plano — a reabertura da base: o retorno dos consumidores e as pendências que pedem regeneração

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 17/11/2026. Falta: a revisão por outro agente (§7) e as respostas da rodada 1 (§5). Nada foi executado |
| Origem | Pedido do Owner, 17/11/2026, depois de ler o que os três consumidores anotaram sobre a `v2.1.0`: "tomar todas as soluções mais robustas, mesmo que inclua regenerar bases e ADR [...] Reabre, resolve e fecha". Na mesma conversa, o Owner incluiu a V5 (a regeneração adiada pela Q47), a V6, a V7, a D63 e a D64 |
| Base | `4d6f797`, sobre a `v2.1.0` (`eb11709`) |
| Entradas lidas | `gdados/docs/alinhamento_entre_projetos.md` §7; `nl_sql/PENDENCIAS.md` item 9 e o parecer de 17/11/2026; `bi-como-codigo/docs/upstream_questions.md` UQ-16 a UQ-20, todos em 17/11/2026 |
| Consumidores durante a fase | O `gdados` segue o desenvolvimento dele contra a `v2.1.0`. O `nl_sql` e o `bi-como-codigo` **esperam a tag desta fase** para reimportar e exportar (Owner, 17/11/2026). Nenhuma janela de leitura do armazém é aberta enquanto o ciclo do Bloco 5 durar |

Este plano não decide o que está nas perguntas do §5. Ele ordena o escopo que o Owner fixou e diz,
para cada item, onde fica o conteúdo dele. O conteúdo de cada item continua no seu dono: Achados,
Pendências, ADR, especificação do pacote, Consumidores.

---

## 1. O escopo

| # | Item | De onde vem | Muda o dado? | Bloco |
|---|---|---|---|---|
| 1 | **F31: os eventos do exercício de *streaming* chegam às views.** No ciclo de 17/11, o `make stream-produce LIMITE=2200` (diário do Bloco 5R, E4) gravou 2.200 eventos no livro da origem, com data do relógio (16/11/2026) e depois da `as_of_date` (2026-09-01). Os eventos se distribuem em `sale_dispatch` (55% dos pesos), recebimento, devolução, ajuste e transferência. A sincronização e o `dbt-build` da E9 os levaram ao `analytics`. O produtor também move `oltp.inventory_balances` (`src/mvp_ed1/streaming/producer.py`, `_mover_saldo`). O BI mediu 984 movimentos `sale` sem pedido, R$ 6.604.745,09 de custo na P08 de novembro, 17.555 unidades de saída na P11 de 2026-T4 e saldos líquidos desses eventos na P12. Não reconferido aqui | UQ-16 do BI | Sim | 2 e 5 |
| 2 | **V5: o giro de estoque muito baixo.** Mediana 0,02 por trimestre e p90 0,49 na P11 depois do ciclo | Pendências, V5 (adiada pela Q47) | Sim | 2 e 5 |
| 3 | **F32: as relações sem descrição não têm guarda.** O pacote em `eb11709` lista 123 relações sem descrição: 40 em `raw_legacy`, 30 em `raw`, 29 em `trusted`, 19 em `staging`, 4 em `snapshots` e 1 em `quarantine`. O Dicionário de Dados §1.1 diz que objeto sem descrição bloqueia a etapa, mas `tests/test_descricao.py` só conta colunas (`TETO_SEM_DESCRICAO`). O "141 → 0" de Consumidores §5 é só das colunas | `gdados`, §7 | Não | 3 |
| 4 | **F33: a nota do custo do GCP está desatualizada no pacote.** A entrada `registro_fase_gcp` de `environments` diz "o custo real entra quando o faturamento fechar" (`src/mvp_ed1/models/pacote.py:97` e o exemplo do pacote). O custo foi lido em 16/11 (Capacidade §2.14), e `environments` não tem entrada para esse documento. O `docs/plano_de_desenvolvimento.md:347` não entra: a frase já vem seguida de "lido em 16/11/2026" | `gdados`, §7 | Não | 4 |
| 5 | **UQ-18: a chave de uma view.** A especificação lista os papéis de `view_rules` sem dizer que a chave é `grain` + `identity`. E `relations.*.grain` é `null` nas 16 views sem uma regra que o explique | BI | Não | 4 |
| 6 | **UQ-19: a auditoria sem a execução.** `view_audits` diz `audited` em `0471f6a`, mas não aponta para a execução das verificações sobre o dado atual | BI | Não | 4 |
| 7 | **Antes → depois medido view a view.** A Q63 deixou o "antes" das 16 views sem medição no ciclo de 17/11. Desta vez, as 16 são capturadas antes e depois da regeneração, e a diferença é publicada por view | Pedido de robustez do Owner; UQ-20 | — | 5 |
| 8 | **D63: o medidor encerra o Beam antes de o ramo de alerta drenar** | Pendências, D63 | Não | 1 |
| 9 | **D64: a chave Fernet do Airflow é inválida** | Pendências, D64 | Não | 1 |
| 10 | **V6: o Python aborta ao desligar o pipeline** | Pendências, V6 | Não | 1 e 5 |
| 11 | **V7: a restauração não registra o tratamento da época que abre** | Pendências, V7 | Não | 1 e 5 |
| 12 | **UQ-17:** a V4 passa a citar também a P12 (o par armazém 1 × variante 30 do legado), se ele continuar igual depois da regeneração | BI | Não | 6 |
| 13 | **UQ-20:** as linhas "Não medido" de Consumidores §5 citam os arquivos `*_depois.csv` dos Blocos 1 e 1b, ou dizem o que é mensurável | BI | Não | 6 |
| 14 | **A ordem das linhas de Consumidores §5:** a linha de 17/11 (`905ba9c`) vem antes da de 16/11 (`d4297ed`, `e1ac94f`) | `gdados`, §7 | Não | 6 |
| 15 | **O cabeçalho dos Achados.** Ele diz que ali vive "o que o `nl_sql` descobriu", mas os F17 a F30 foram achados aqui | `nl_sql`, item 9 | Não | 6 |

**Fica fora**, com o motivo:
- **Trocar o código `GW-OK`:** mudaria o dado, e o significado já está declarado (`nl_sql`, item 9).
- **A D43 e a V1 a V3:** o Owner não as incluiu, e nenhuma muda o que os consumidores leem.

---

## 2. Os blocos, na ordem

### Bloco 0 — a abertura (só documentos)

1. Registrar o F31, o F32 e o F33 nos [Achados](docs/achados_nl_sql.md), pela regra de entrada (Consumidores
   §4), cada um com a origem (o consumidor que o levantou) e este plano como destino.
2. Uma linha `prevista` em Consumidores §5 para cada mudança que alcança um consumidor: o dado das 16 views
   (itens 1, 2 e 7), o pacote (itens 3 a 6) e os textos (itens 12 a 15).
3. Abrir a D93 nas Pendências para o item 1. A decisão vira ADR pela Q64.
4. O README passa a apontar para este plano no estado do projeto.

### Bloco 1 — a operação (código e testes, sem dado)

Vem antes do ciclo, porque o ciclo passa por cada um destes itens e os mede.

- **D64:** a forma que a Q66 escolher. Recomendada: a opção (a) das Pendências, com a geração em base64
  seguro para URL nos dois lugares do `Makefile`, um teste em `tests/test_makefile.py` e a chave da máquina
  trocada ao recriar o Airflow.
- **D63:** a forma que a Q65 escolher. Recomendada: a opção (a) das Pendências. O medidor espera, com prazo,
  um sinal do ramo de alerta, e a restauração reposiciona o grupo do Beam no início do *log*.
- **V7:** o `make recovery-restore` passa a chamar o `make ledger-treatment` no passo que constrói a
  quarentena da captura, com teste de que a época aberta sai com o registro.
- **V6:** primeiro a medida, depois a correção. O que fica no ar no desligamento: *threads daemon* e o
  `stderr` do Prism. Teste de que o encerramento limpo sai com o código 0. Se a causa não aparecer, a V6
  volta ao Owner com a medida, sem correção às cegas.

### Bloco 2 — a regeneração declarada (F31 e V5)

1. **Medir o alcance do produtor** antes de escolher a forma (Q64): que tabelas da origem ele escreve
   (`inventory_movements`, `inventory_balances` e outras); que modelos e views leem cada uma; que
   *snapshots* capturam os saldos. Só leitura, no código e no armazém.
2. **A D93 e o ADR-0057**, com a forma escolhida e a contrapartida na fase GCP. O contrato do evento
   (Modelo de Dados §5) muda se a forma marcar a origem.
3. **V5:** a declaração em `generator/geracao.yml` (abertura e compras pela demanda) e a meta da Q67, medida
   em memória no varejo antes do ciclo, como a V4 fez (Q42).
4. Guardas novas, uma por correção: para o F31, nenhum movimento de venda sem pedido nas views de consumo e
   nenhum evento do exercício no estado publicado, conforme a forma; para a V5, o giro dentro da faixa
   declarada.
5. A revisão integral do Owner sobre o declarativo: `geracao.yml`, o ADR e as guardas.

### Bloco 3 — as descrições das relações (F32)

1. Descrever as 123 relações no `.yml` de cada camada. Os *sources* `raw` e `raw_legacy` descrevem a tabela
   de origem; os modelos e os *snapshots* descrevem o grão e o papel.
2. Estender `tests/test_descricao.py` às relações, com **teto zero** e uma mensagem que nomeia cada relação
   sem descrição.
3. Revisão integral do Owner: é declarativo, e são 123 textos. É o maior volume da fase (risco R14).

### Bloco 4 — o pacote (F33, UQ-18, UQ-19)

1. **F33:** a nota de `registro_fase_gcp` atualizada, e uma entrada nova em `environments` para a Capacidade
   §2.14, de onde os portais leem o custo.
2. **UQ-18:** a especificação diz que a chave de uma view é a união das colunas de papel `grain` e
   `identity` em `view_rules`, e que `relations.*.grain` das views é `null` porque o grão delas está em
   `view_rules`. Um teste guarda que essa chave é única em cada view do armazém.
3. **UQ-19:** cada entrada de `view_audits` ganha os ids das suas verificações em `checks`, de onde vêm o
   resultado e a data. É campo novo do formato 1 (Q13), e o esquema e o exemplo mudam junto.

### Bloco 5 — o ciclo

Mesma forma do ciclo do Bloco 5R, com um diário próprio (`data/medicoes/diario_reabertura.md`) e
sem `FORCE`.

1. **O antes:** captura das 16 views, numa transação `REPEATABLE READ READ ONLY`, sobre o armazém da
   `v2.1.0`, com SHA-256 de cada saída.
2. A regeneração das duas origens, com a memória do armazém mantida, como no Bloco 5R.
3. O exercício de *streaming* sob a forma da D93, com a medição da D63 e a observação da V6.
4. A sincronização, o `dbt-build`, a procedência `verified`, o `check` e a restauração (com a V7).
5. **O depois:** a mesma captura das 16 views, e a diferença por view publicada em Consumidores §5 (linhas
   e somas antes e depois, por view).
6. As guardas novas passam no armazém. A P11 é medida contra a meta da V5.

### Bloco 6 — os textos depois do ciclo

UQ-17, UQ-20, a ordem de Consumidores §5 (Q70) e o cabeçalho dos Achados.

### Fechamento

- `make check` verde; catálogo, dicionário, linhagem e pacote regenerados.
- A revisão por outro agente, por bloco, e a do fechamento.
- O aceite do Owner e a *tag* (Q69).
- Um aviso único aos três consumidores, com a *tag* e Consumidores §5.
- O que **não** foi provado continua declarado: o BigQuery (L9).

---

## 3. O que já foi conferido para escrever este plano (sem efeito)

- **Os 123 do F32:** contados no pacote em `4d6f797`, igual a `eb11709` (`description_gaps` com
  `column: null`).
- **As escritas do produtor:** `oltp.inventory_movements`, com os tipos e os pesos de `PESOS`, e
  `oltp.inventory_balances`, por `_mover_saldo` em `src/mvp_ed1/streaming/producer.py`. Por isso, filtrar só
  os movimentos não basta para a P12. É o que a medida do Bloco 2 decide.
- **O diário do Bloco 5R:** E4 (2.200 eventos, às 02:57) e E9 (a sincronização e o `dbt-build`, às 03:05),
  nessa ordem.
- **O `plano_de_desenvolvimento.md:347`:** a frase do custo já traz a leitura de 16/11. Só o pacote e o exemplo
  estão desatualizados.

---

## 4. Riscos

| Risco | Como o plano o trata |
|---|---|
| A regeneração é destrutiva e refaz todos os números conferidos | O antes → depois por view (item 7) mede o que muda. As guardas passam no armazém antes do aceite |
| R11, os ambientes pesados | Os alvos guardados fazem a troca. O ciclo segue a ordem do Bloco 5R |
| R14, o volume que ninguém revisa | As 123 descrições e o `geracao.yml` vão à revisão integral do Owner, e as guardas cobrem o derivado |
| Consumidor que lê no meio do ciclo | Nenhuma janela de leitura durante o Bloco 5. O `nl_sql` e o BI esperam a *tag* |
| A forma do F31 se mostrar maior que o previsto | A Q64 só é respondida depois da medida do Bloco 2 |

---

## 5. Decisões pedidas ao Owner — rodada 1

A numeração continua a do plano da base dos consumidores, para que uma `Qnn` citada em Consumidores §5
não seja ambígua.

| # | Pergunta | Opções | Recomendação |
|---|---|---|---|
| Q64 | A forma da correção do F31 (D93, ADR-0057) | **(a)** O produtor marca a origem do evento como exercício. O `analytics` conserva o evento marcado, as views de consumo e os saldos publicados o excluem por regra declarada, e uma guarda o confere. Nada é descartado. **(b)** Depois do exercício, a origem volta ao corte de antes dele, e o estado publicado não traz resíduo do teste. **(c)** O produtor emite eventos coerentes com o domínio, com venda ligada a pedido e dentro da janela, o que cruza domínios. **(d)** O produtor deixa de emitir venda: não resolve os saldos nem o custo dos outros tipos | **Provisória: (a)**, como num ambiente corporativo: o evento de teste fica identificável e fora do que se publica, sem descarte. A resposta só vem depois da medida do Bloco 2, item 1: se os saldos e os *snapshots* tornarem a (a) cara demais, a (b) passa à frente |
| Q65 | A D63 | As opções (a), (b) e (c) das Pendências | **(a)** |
| Q66 | A D64 | As opções (a) e (b) das Pendências | **(a)** |
| Q67 | A meta do giro da V5 | **(a)** Uma faixa declarada para a mediana trimestral da P11, a fixar com a medida em memória. **(b)** Só "maior que hoje", sem faixa | **(a)**. A faixa é escolha sua: a proposta parte da medida em memória, e não de um número de fora |
| Q68 | Medir o antes → depois das 16 views neste ciclo | Sim / Não, como a Q63 | **Sim**: os dois consumidores que esperam vão comparar valores, e o diff daqui evita que cada um o refaça |
| Q69 | A *tag* desta fase | `v2.2.0` / `v2.1.1` | **`v2.2.0`**: o dado muda |
| Q70 | A ordem de Consumidores §5 | Corrigir a ordem / Corrigir e guardar com teste a ordem por data | **Corrigir e guardar** |

---

## 6. Definição de pronto aplicada

A do `CLAUDE.md` §7, e mais:
- os quinze itens do §1 respondidos: feitos, ou devolvidos ao Owner com a medida;
- o antes → depois das 16 views publicado;
- os três consumidores avisados uma vez, com a *tag*.

---

## 7. Rodadas de revisão

Nenhuma ainda. A primeira é a deste plano, antes de qualquer execução.
