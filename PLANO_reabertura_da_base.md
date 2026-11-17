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
| 16 | **F34: o destino das chaves estrangeiras fora do pacote.** Em `eb11709`, os 76 testes `relationships` trazem a relação e a coluna testadas, mas não as referenciadas, e as 26 PKs e 58 FKs de `analytics` (ADR-0056) não estão no pacote. A página de estrutura do `gdados` precisa delas para o diagrama entidade-relacionamento | `gdados@52c4359`, §7 (entrou depois de `cc70fc6`) | Não | 4 |

**Fica fora**, com o motivo:
- **Trocar o código `GW-OK`:** mudaria o dado, e o significado já está declarado (`nl_sql`, item 9).
- **A D43 e a V1 a V3:** o Owner não as incluiu, e nenhuma muda o que os consumidores leem.

---

## 2. Os blocos, na ordem

### Bloco 0 — a abertura (só documentos)

1. Registrar o F31 a F34 nos [Achados](docs/achados_nl_sql.md), pela regra de entrada (Consumidores
   §4), cada um com a origem (o consumidor que o levantou) e este plano como destino.
2. Uma linha `prevista` em Consumidores §5 para cada mudança que alcança um consumidor: o dado das 16 views
   (itens 1, 2 e 7), o pacote (itens 3 a 6) e os textos (itens 12 a 15).
3. Abrir a D93 nas Pendências para o item 1. A decisão vira ADR se a forma da Q64 pedir.
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

1. **Medir o alcance do produtor** antes de fechar a forma (Q64). Só leitura, no código e no armazém.
   - Que tabelas da origem ele escreve: `inventory_movements`, `inventory_balances` e outras.
   - Que modelos e views leem cada uma.
   - **Se a regeneração tira do armazém os eventos do exercício.** A `fact_inventory_movement` é incremental,
     o livro quente é *append-only* e o `inventory_balances` chega por `dedup_history`. O que decide é como o
     ciclo do Bloco 5R tratou o livro e as épocas ao regenerar.
2. **A D93**, com a forma escolhida e a contrapartida na fase GCP. Na forma (e), não há ADR de tratamento de
   dados: muda a ordem do ciclo e entra uma guarda. As formas (a) e (b) pedem ADR (0057), porque mudam o
   contrato do evento (Modelo de Dados §5) ou a restauração.
3. **V5:** a declaração em `generator/geracao.yml` (abertura e compras pela demanda) e a meta da Q67, medida
   em memória no varejo antes do ciclo, como a V4 fez (Q42).
4. Guardas novas, uma por correção:
   - para o F31, nenhum movimento depois da `as_of_date` e nenhuma venda sem pedido no `analytics`;
   - para a V5, o giro dentro da faixa declarada.
5. Uma linha na [Execução Local](docs/execucao_local.md) diz que o `stream-produce` suja o estado publicado e
   que a guarda acusa isso.
6. A revisão integral do Owner sobre o declarativo: `geracao.yml`, a D93 (e o ADR, se houver) e as guardas.

### Bloco 3 — as descrições das relações (F32)

1. Descrever as 123 relações no `.yml` de cada camada. Os *sources* `raw` e `raw_legacy` descrevem a tabela
   de origem; os modelos e os *snapshots* descrevem o grão e o papel.
2. Estender `tests/test_descricao.py` às relações, com **teto zero** e uma mensagem que nomeia cada relação
   sem descrição.
3. Revisão integral do Owner: é declarativo, e são 123 textos. É o maior volume da fase (risco R14).

### Bloco 4 — o pacote (F33, UQ-18, UQ-19, F34)

1. **F33:** a nota de `registro_fase_gcp` atualizada, e uma entrada nova em `environments` para a Capacidade
   §2.14, de onde os portais leem o custo.
2. **UQ-18:** a especificação diz que a chave de uma view é a união das colunas de papel `grain` e
   `identity` em `view_rules`, e que `relations.*.grain` das views é `null` porque o grão delas está em
   `view_rules`. Um teste guarda que essa chave é única em cada view do armazém.
3. **UQ-19:** cada entrada de `view_audits` ganha os ids das suas verificações em `checks`, de onde vêm o
   resultado e a data. É campo novo do formato 1 (Q13), e o esquema e o exemplo mudam junto.

4. **F34:** `relations.*.primary_key` e `relations.*.foreign_keys` (`column`, `references_relation`,
   `references_column`), derivados pela **mesma regra** que instala as chaves (`dbt/macros/chaves.sql`,
   `_chaves_declaradas`): as PKs pelas colunas com `constraints: primary_key`, e as FKs pelos testes
   `relationships` cujo `to` é um modelo de `analytics`. Cada teste `relationships` do pacote ganha o destino
   (`to` e `field`). Um teste guarda que o pacote traz as mesmas PKs e FKs que a macro instala.

### Bloco 5 — o ciclo

Mesma forma do ciclo do Bloco 5R, com um diário próprio (`data/medicoes/diario_reabertura.md`) e
sem `FORCE`.

1. **O antes:** captura das 16 views, numa transação `REPEATABLE READ READ ONLY`, sobre o armazém da
   `v2.1.0`, com SHA-256 de cada saída.
2. **O exercício de *streaming*, na forma (e):** o produtor, a comparação dos dois caminhos, a medição da D63
   e a observação da V6, sobre o estado que a regeneração vai descartar.
3. A regeneração das duas origens, com a memória do armazém mantida, como no Bloco 5R.
4. A publicação **sem produtor**: o *snapshot* do CDC entrega o livro regenerado, como na C3 do Bloco 5R. Em
   seguida, a sincronização, o `dbt-build`, a procedência `verified`, o `check` e a restauração (com a V7).
5. **O depois:** a mesma captura das 16 views, e a diferença por view publicada em Consumidores §5 (linhas
   e somas antes e depois, por view).
6. As guardas novas passam no armazém. A P11 é medida contra a meta da V5.

Se a Q64 ficar com outra forma, os passos 2 a 4 voltam à ordem do Bloco 5R.

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
  os movimentos não basta para a P12.
- **Os caminhos até o armazém:** os movimentos chegam pelo CDC, e o Airbyte só os recarrega em `full_refresh`
  para reconciliar (`airbyte/streams.yml`). Os saldos chegam em `dedup_history`. O livro é *append-only* por
  contrato (Modelo de Dados), e a `fact_inventory_movement` é incremental.
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
| Q64 | A forma da correção do F31 (D93) | **(e)** O exercício roda **antes** da regeneração, sobre o estado que ela vai descartar. Depois de regenerar, publica-se sem produtor. Uma guarda no estado publicado falha o `check` se aparecer movimento depois da `as_of_date` ou venda sem pedido. **(a)** O produtor marca a origem do evento como exercício, e as views e os saldos publicados o excluem por regra declarada (contrato do evento e ADR). **(b)** Depois do exercício, a origem e o armazém voltam ao corte de antes dele, pela restauração. **(c)** O produtor emite eventos coerentes com o domínio, com venda ligada a pedido. **(d)** O produtor deixa de emitir venda: não resolve os saldos nem o custo dos outros tipos. **Descartadas (Owner perguntou, 17/11):** apagar as linhas ou trocar células, porque o livro é *append-only* por contrato, o CDC levaria a edição ao livro quente como evento novo, o histórico do `inventory_balances` (`dedup_history`) e as capturas certificadas a registrariam, e as regras 3 e 4 do `CLAUDE.md` a proíbem; e o estorno (linhas compensatórias), que devolve o saldo mas não tira a venda bruta da P11 nem o custo da P08, e deixa as datas depois da `as_of_date` | **(e)**, se a medida do Bloco 2, item 1, confirmar que a regeneração tira do armazém os eventos do exercício (a fato de movimentos é incremental). Resolve os saldos sem tocar em nenhuma linha, não muda o contrato do evento e não pede ADR de tratamento de dados. A guarda torna visível qualquer exercício futuro sobre o estado publicado. Fica declarado na D93 que a (c) é o caminho se um dia o produtor simular operação continuada de verdade (intenção da fase GCP). Se a medida não confirmar, a (b) |
| Q65 | A D63 | As opções (a), (b) e (c) das Pendências | **(a)** |
| Q66 | A D64 | As opções (a) e (b) das Pendências | **(a)** |
| Q67 | A meta do giro da V5 | **(a)** Uma faixa declarada para a mediana trimestral da P11, a fixar com a medida em memória. **(b)** Só "maior que hoje", sem faixa | **(a)**. A faixa é escolha sua: a proposta parte da medida em memória, e não de um número de fora |
| Q68 | Medir o antes → depois das 16 views neste ciclo | Sim / Não, como a Q63 | **Sim**: os dois consumidores que esperam vão comparar valores, e o diff daqui evita que cada um o refaça |
| Q69 | A *tag* desta fase | `v2.2.0` / `v2.1.1` | **`v2.2.0`**: o dado muda |
| Q70 | A ordem de Consumidores §5 | Corrigir a ordem / Corrigir e guardar com teste a ordem por data | **Corrigir e guardar** |

---

## 6. Definição de pronto aplicada

A do `CLAUDE.md` §7, e mais:
- os dezesseis itens do §1 respondidos: feitos, ou devolvidos ao Owner com a medida;
- o antes → depois das 16 views publicado;
- os três consumidores avisados uma vez, com a *tag*.

---

## 7. Rodadas de revisão

### Rodada 1 — codex2, sobre `cc70fc6` (17/11/2026)

Relatório: `data/medicoes/reabertura/codex2_plano_r1.md`, fora do Git.
- **Conclusão do Codex:** nada impede o Bloco 0. O Bloco 5 tem 3 bloqueantes (RVRB-1-01, 02 e 06) e há 5 ajustes
  (03, 04, 05, 07 e 08).
- **A forma (e) confirmada** pela evidência do 5R: o descarte completo retira os eventos do exercício.
- **Posição do autor:** `data/medicoes/reabertura/parecer_claude_r1.md`. Concorda com os oito.
- **A aplicar no plano.** A rodada 2 vem depois disso.
- **O item 16 (F34)** entrou depois do objeto da rodada, a partir do canal do `gdados`.
