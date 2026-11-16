# ADR-0056 — Declarar as chaves de `analytics` com contrato, e manter as FKs fora da execução dos modelos

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 16/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | Q4 e Q34 a Q38 do [plano da base dos consumidores](../../PLANO_base_dos_consumidores.md) (§6, rodadas 1 e 10) |
| Substitui / é substituída por | — (complementa o [ADR-0054](0054-procedencia-do-armazem-no-log-de-execucao.md), sem substituí-lo) |

## Contexto

O `nl_sql` mediu que as chaves de `analytics` só existiam como teste (**F10**, [Achados](../achados_nl_sql.md)):
os `unique` e as `relationships` provam os valores, mas não chegam ao BigQuery como `PRIMARY KEY` e
`FOREIGN KEY NOT ENFORCED`. São essas *constraints* que o Gemini e o Knowledge Catalog usam para
descobrir as junções. A Q4-a fixou a direção: *contract* e *constraints* nos modelos de `analytics`, com
PK e FK declaradas e, no PostgreSQL, impostas. A revisão do plano (RVC-1-01) exigiu que o ADR declarasse
o **ciclo de vida** delas, porque o dbt recria cada tabela de `analytics` por troca de nomes e apaga a
antiga com `drop … cascade`, e a `fact_inventory_movement` é incremental.

O desenho está no Bloco 6 do plano, com o que foi medido antes de decidir. Ele passou por seis rodadas
de revisão (rodadas 46 a 51, `codex2_bloco6_desenho_r1.md` a `r6.md`), que mudaram o desenho três vezes:

- **A FK dentro do *contract* se perde.** Ao recriar uma dimensão, o `cascade` leva a FK de toda fato
  que a aponta. A fato em tabela a recria na sua vez; a incremental não, e perde a FK já na segunda
  execução normal. Com a dimensão sem uma chave, a incremental recebe os órfãos calada.
- **Instalar a FK só no fim trava com quatro *threads*.** Duas tabelas ligadas por FK, sem `ref` entre
  elas, se reconstroem ao mesmo tempo, e o `drop … cascade` de uma pede trava na FK da outra
  (`deadlock detected`). Fica um `__dbt_backup` com as FKs das fatos apontando para ele, e toda execução
  seguinte falha. A primeira sonda, de uma *thread*, não mostrava isso.
- **Nada impede duas invocações ao mesmo tempo.** O log do ADR-0054 detecta a sobreposição, não a barra.
  Mas o log registra também as duas capturas da DAG, que rodam em paralelo de propósito, e a prova
  `test_fato`, que chama um `dbt run` de dentro da própria linha aberta.
- **O `dbt retry` chega aos *hooks* com a seleção vazia**, e pode reconstruir `analytics` sem dizer o
  quê. A DAG o usa nas falhas transitórias de toda tarefa.

Medido também: o *contract* do PostgreSQL pega a troca do tipo base, inclusive na incremental, mas não
compara precisão, escala nem comprimento. O `numeric(12,6)` calculado numa coluna declarada
`numeric(12,4)` grava arredondado e calado. O BigQuery recusa o tipo parametrizado no `cast` da checagem
do contrato. As sondas e as saídas estão em `data/medicoes/base_consumidores/bloco6_sonda/`.

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **PK no *contract*; FKs das `relationships`, retiradas no começo e instaladas no fim de cada execução de `analytics`** (a escolhida, Q34) | Uma declaração só, a do teste; um ciclo único para tabela e incremental; nenhuma trava entre modelos durante a execução; o órfão faz a execução falhar | As 58 FKs se revalidam a cada execução de `analytics`; entre uma falha e a execução seguinte elas ficam de fora; exige uma invocação de cada vez |
| FK no *contract*, reinstalada nos *post-hooks* das dimensões e da incremental | Usa o mecanismo do dbt | Duas declarações; depende da ordem do grafo (no `RESET=1` a dimensão nova chega antes da fato velha); o mesmo `cascade` concorrente que travou a sonda |
| FK instalada só no fim, sem retirar no começo | Simples | Travou em *deadlock* com quatro *threads* (medido) |
| Mudar a materialização das dimensões para não recriar a tabela | Sem `cascade` | Reabre o [ADR-0016](0016-materializacao-por-camada.md) |
| Exclusão global no log, uma linha aberta por vez (Q38) | Simples de enunciar | Recusaria as capturas paralelas da DAG e o `dbt run` aninhado da `test_fato` |
| Trava consultiva de sessão do PostgreSQL (Q38) | Não muda o log | Mecanismo novo: uma sessão própria do começo ao fim, com a adesão de cada chamador; não medido |
| Não impedir a concorrência (Q38) | Nenhuma mudança | A intercalação que devolve as FKs no meio de outra execução continua possível |
| `data_type` derivado a cada `make catalog-derivados` (Q35) | Nunca desatualiza | O contrato passaria a seguir o modelo, e mudança de tipo não falharia nunca |
| `data_type` escrito à mão (Q35) | Intenção explícita | 513 declarações sem revisão real (R14) |
| Também o `not_null` como *constraint*, ou as chaves no pacote (Q36) | Mais metadado | No BigQuery o `not_null` vira `REQUIRED`, imposto; as chaves no pacote mudam o esquema dele, e o alvo do F10 é o banco |

## Decisão

As chaves de `analytics` passam a ser **declaradas com contrato**, e as FKs vivem **entre execuções,
nunca durante** uma.

**O contrato.** `+contract: {enforced: true}` em toda a camada, no `dbt_project.yml`. As 513 colunas
ganham `data_type`: o tipo de hoje, escrito uma vez por script, a partir do tipo que o `select` sem
linhas de cada modelo calcula, lido do cursor com o `typmod` (Q35). Onde o BigQuery pede outro nome, a
expressão em linha escolhe por alvo:

- `character varying` → `string`;
- `timestamp with time zone` → `timestamp`;
- `numeric(p,s)` → `numeric`. A escala no BigQuery continua a do SQL (`decimal_fixo`).

Depois disso o tipo é declaração. Uma guarda no `make test` compara o tipo calculado com o declarado e
detecta a mudança de modificador que o contrato não pega. Ela detecta depois do *build*; não impede o
que já foi gravado.

**A PK.** Uma por modelo, na chave substituta, como `constraints: [{type: primary_key}]` da coluna,
dentro do contrato (26).

**As FKs.** As 58 `relationships` de `analytics` para `analytics` são a declaração. Nada se declara
duas vezes. Duas macros agem só em `run` e `build` cuja seleção tem modelo de `analytics`, ou que
chegam à execução com a seleção vazia (o `dbt retry`). Agem também só com a abertura desta invocação
confirmada no log:

- no `on-run-start`, depois da abertura, **retirar toda FK de `analytics`**;
- no `on-run-end`, depois do acesso e antes do fecho, **instalar a PK declarada que falta e cada FK**,
  com o nome `fk_<tabela>__<coluna>`, conferindo a existência pela definição inteira.

**Uma invocação de `analytics` de cada vez** (Q38). Complementa o ADR-0054, que continua valendo. A
abertura grava um escopo `analytics` quando a invocação cumpre o mesmo predicado das macros, e um índice
único parcial sobre o escopo das linhas `started` torna a admissão atômica. A recusada não muda
*constraint*, e os nós dela são pulados. As capturas, as mutações fora do dbt, o `seed` e o `snapshot`
ficam fora do escopo e seguem como hoje.

**A falha.** O órfão faz a instalação falhar, a execução sai com erro, o fecho não grava e a procedência
fica `not_verified`. A recuperação segue esta ordem:

1. o diagnóstico, só de leitura (*anti-join* da fato com a dimensão);
2. confirmar que a execução que falhou terminou;
3. o abandono da linha dela pelo custodiante;
4. corrigir a causa por código versionado;
5. uma execução admitida;
6. conferir a população e as *constraints*.

O `--full-refresh` da incremental não é recuperação garantida, porque as junções da fato deixam de fora o
movimento cujo destino falta. **Nenhuma linha se apaga para a FK passar**: remoção ou outro destino é
tratamento novo, com motivo e decisão do Owner.

**O alcance** (Q36). PK e FK, e só. O `not_null` e as chaves naturais continuam como teste. O pacote não
ganha campo de chaves, e o consumidor as lê no banco e no `.yml`.

**A prova.** No projeto real, na entrega:

- a instalação inicial;
- a segunda execução incremental;
- a reconstrução só de dimensão;
- o tempo das 58 FKs;
- a ausência de *deadlock*;
- duas invocações sobrepostas;
- o retry;
- a execução interrompida;
- a população da fato.

O `RESET=1` se prova no ciclo do Bloco 5R, que já o roda (Q37); até lá é pendência declarada.

## Consequências

- **Positivas:**
  - o BigQuery passa a receber `PRIMARY KEY` e `FOREIGN KEY NOT ENFORCED`, o que o F10 pedia;
  - no PostgreSQL, a FK impõe: o órfão deixa de entrar calado na fato incremental e passa a fazer a
    execução falhar;
  - o tipo de cada coluna vira declaração conferida, e o pacote publica `data_type` nas 513 colunas;
  - duas execuções de `analytics` deixam de poder se intercalar.
- **Negativas:**
  - as 58 FKs se retiram e se revalidam a cada execução de `analytics`: uma vez por ciclo da DAG sem
    retentativa, mais uma por retry de `run` ou `build` com trabalho restante. O tempo não foi medido;
  - entre uma execução que falha ou é interrompida e a seguinte admitida, as FKs ficam de fora. `dbt
    test` e `run-operation` não as repõem;
  - depois de toda falha que pule o fecho, nenhuma execução de `analytics` é admitida até o abandono pelo
    custodiante. A falha que antes só bloqueava a procedência passa a parar o pipeline de `analytics`;
  - o retry de outra camada também entra na exclusão e revalida as FKs, por cautela;
  - a guarda de tipo detecta a mudança de modificador depois do *build*, não antes;
  - as macros, o escopo e o índice do log são código a manter, com contraprovas.
- **Paridade com o GCP:**
  - a PK sai pelo contrato do dbt-bigquery, que a escreve `NOT ENFORCED`;
  - as FKs saem pelas mesmas macros, por despacho de adaptador (`alter table … add constraint … not
    enforced`, a existência por `INFORMATION_SCHEMA.TABLE_CONSTRAINTS`);
  - o escopo e o índice valem para o log do BigQuery pelo mesmo `governance`;
  - nada disso foi exercitado no GCP nesta fase (L9), nem o efeito no Gemini e no Knowledge Catalog.
- **Documentos a atualizar** (com a implementação):
  - [Qualidade de Dados](../qualidade_de_dados.md): o contrato e as *constraints* em `analytics`, ao lado
    do `relationships`;
  - [Materialização](../materializacao.md): as FKs fora da execução dos modelos;
  - [Governança de Dados](../governanca_de_dados.md), a linha da procedência: o escopo `analytics` e a
    admissão;
  - [Execução Local](../execucao_local.md): a recuperação na ordem acima e a recusa da execução
    sobreposta;
  - [Consumidores](../consumidores.md) §5: a `prevista` do `data_type` antes, e a `feita` depois;
  - o [plano da base dos consumidores](../../PLANO_base_dos_consumidores.md), onde está o desenho.
