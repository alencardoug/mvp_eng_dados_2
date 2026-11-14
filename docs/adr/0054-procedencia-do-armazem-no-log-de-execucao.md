# ADR-0054 — Provar a procedência do armazém pelo log de execução do dbt

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 15/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | L5 do [plano da base dos consumidores](../../PLANO_base_dos_consumidores.md) (§6, rodada 5) |
| Substitui / é substituída por | — |

## Contexto

Nada provava qual *commit* construiu o armazém que o `bi-como-codigo` lê. A procedência que o pacote de
metadados da D91 declarava era a dos artefatos do dbt (`manifest.json`, `run_results.json`), não a do
banco, e por isso o pacote dizia `provenance.warehouse.status: not_verified`. O BI captura o armazém como
custodiante, numa transação de leitura aberta numa janela que o Owner autoriza, e queria responder ali
mesmo: "este armazém foi construído por esta execução, deste *commit*".

O [ADR-0023](0023-escopo-do-schema-governance.md) já tinha declarado em `governance` o conjunto *log de
execução* ("cada execução de pipeline: início, fim, resultado, versão do código"), sem materializá-lo.
O [ADR-0044](0044-certificar-cada-captura-do-legado-por-conteudo.md) materializou outro conjunto do mesmo schema,
`legacy_captures`, escrito em duas fases. O Owner decidiu em 15/11/2026 materializar o log para o dbt,
com este ADR e com a mudança do esquema do pacote.

O desenho passou por seis rodadas de revisão (`codex1_l5_desenho_r1` a `r6`), e a cada uma a primeira
ideia — "a última linha do log diz quem construiu" — se mostrou mais larga do que o que ela prova: uma
execução parcial, um `dbt retry`, uma falha no fim, uma escrita fora do dbt (o descarte dos *snapshots*, o
teste que adultera a fato, a restauração da memória, a sincronização do Airbyte com `drop_cascade`)
mudavam o armazém sem mudar a resposta. A garantia que sobrou é estreita de propósito.

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **Log em duas fases, garantia estreita** (a escolhida) | Responde à pergunta do BI na própria transação de leitura; toda execução fica registrada, e só a que pode sustentar a procedência a sustenta; usa o mecanismo de `legacy_captures` e um conjunto que a ADR-0023 já previa | Muita coisa fica `not_verified` (a DAG, que roda por camada, nunca verifica sozinha); exige que toda escrita fora do dbt se registre; regras operacionais novas (o abandono, o *checkout* parado) |
| Manter `not_verified` | Nenhum custo; o contrato já dizia que a procedência é a dos artefatos | O BI continua sem evidência; a lacuna que a L5 levantou fica aberta |
| A última linha do log, sem condições | Simples | Afirma mais do que prova: uma execução parcial ou uma escrita fora do dbt deixam o armazém de outro estado com a linha de um *build* anterior |
| Uma impressão digital do estado das camadas, conferida na leitura | Pegaria qualquer escritor, inventariado ou não | Conferir dado (e não só definição) exige varrer as tabelas ou depender de contadores que zeram no reinício; muito mais caro, e não pedido |

## Decisão

O armazém registra cada execução do dbt que o escreve, e cada mutação suportada feita fora dele, em
`governance.dbt_invocations`, em duas fases; a *view* `governance.warehouse_provenance` diz `verified` só
quando a última execução é um `build` integral, aprovado, de *commit* conhecido e limpo, com os insumos
confirmados, sem nada aberto nem sobreposto — e `not_verified`, com o motivo, em qualquer outro caso.

Os termos da garantia, que o BI e o pacote leem:

- **O que ela afirma:** o código e a invocação da **última execução integral elegível**, sob as
  materializações declaradas. Não afirma que essa invocação recriou cada linha: o `make dbt-build` não é
  `--full-refresh`, a fato incremental relê só a janela de atraso do ramo `retail`, e os *snapshots*
  guardam versões históricas por desenho. Não certifica a origem de cada linha retida.
- **Integral é medido**, não lido dos argumentos: os resultados cobrem todo nó executável do grafo. O
  `dbt retry` e o `--select` não passam.
- **Cada fase confirma a própria escrita.** A linha aberta (falha, interrupção, *hook* de acesso que
  falhou antes do fecho) **bloqueia** a procedência, porque uma execução antiga pode ainda estar escrevendo.
  Ela sai do caminho só por ato explícito do custodiante (`make governance-abandonar`), que a marca
  `abandoned` e nunca a dá por sucesso. É regra operacional nova.
- **As escritas fora do dbt** se registram pela mesma função: o descarte dos *snapshots*, a adulteração da
  fato pelo `make test FATO=1`, a restauração da memória e toda sincronização do Airbyte (que abre antes do
  disparo e só fecha no estado terminal observado do *job*). Um teste estático impede o escritor novo
  calado, com alcance lexical declarado.
- **O log não é memória:** o `pg_dump` da memória o exclui, e a restauração não o substitui.
- **Precondições operacionais:** o *checkout* fica parado enquanto o dbt roda (um arquivo editado e
  desfeito **dentro** do *build* não é visto); as camadas de **entrada** (`raw`, `raw_legacy`) mudam sem o
  dbt, e a garantia é sobre o código, não sobre o dado de entrada estar parado — uma view de consumo,
  `skus_below_reorder_point`, lê o *stream* ao vivo.

O pacote de metadados passa a ler essa *view* — a única leitura do banco que ele faz — e diz `verified` só
se a execução verificada é a do *manifest*.

## Consequências

- **Positivas:** o BI responde "este armazém é deste *commit*" na transação de captura, com o motivo quando
  não pode; o pacote ganha `verified` com o mesmo critério; toda execução e toda escrita suportada fora do
  dbt ficam registradas, permanentemente, no conjunto que a ADR-0023 previa.
- **Negativas:** a procedência é `not_verified` na maior parte do tempo — depois de qualquer execução
  parcial, da DAG, de uma sincronização — e o custodiante tem de rodar `make dbt-build` de um *commit*
  limpo antes de abrir a janela; toda escrita nova fora do dbt precisa entrar no registro, e a guarda só a
  vê lexicalmente; a linha aberta exige intervenção humana; o `pg_dump` e o `pg_restore` da memória ficam
  mais complicados; o pacote deixa de ser gerado só de artefatos.
- **Paridade com o GCP:** no BigQuery, o mesmo log é uma tabela do *dataset* `governance`, escrita pelos
  `on-run-start` e `on-run-end` do dbt, que o adaptador do BigQuery executa igual; o `INFORMATION_SCHEMA.JOBS`
  do projeto é a evidência complementar das escritas, e a sincronização do Airbyte no Composer passa pelo
  mesmo funil. O relógio é o do serviço (`CURRENT_TIMESTAMP()`), e a identidade vira `GENERATE_UUID()` com
  o instante do serviço para a ordem.
- **Documentos a atualizar:** [Pacote de Metadados](../pacote_de_metadados.md) (o estado `verified`, os
  campos novos, a leitura do banco) e o esquema dele; [Consumidores](../consumidores.md) §5 (o aviso) e §3
  (o custodiante roda o *build* limpo antes da janela); [Execução Local](../execucao_local.md) (o
  `make governance-abandonar`); [Governança de Dados](../governanca_de_dados.md) (o log de execução
  materializado); o [plano da base dos consumidores](../../PLANO_base_dos_consumidores.md), onde está o
  desenho. Os documentos mudam com a implementação, na mesma entrega dela.
