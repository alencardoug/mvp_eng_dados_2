# ADR-0055 — Declarar uma vez os domínios de valores e as métricas, e derivar o resto

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 15/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | Q3, Q15, Q16, Q17 e Q18 do [plano da base dos consumidores](../../PLANO_base_dos_consumidores.md) (§6, rodadas 1 e 6) |
| Substitui / é substituída por | — |

## Contexto

O `nl_sql` mediu o que uma ferramenta consegue fazer lendo só a governança deste projeto
([Achados](../achados_nl_sql.md)). Duas lacunas pesaram:

- **F7** — as colunas categóricas não diziam o que cada valor significa. Só 14 tinham
  `accepted_values`, e nenhuma lista explicava os valores: que `returned` ainda é venda realizada, que
  `UNK` é o membro desconhecido. O `nl_sql` precisou de 42 domínios e 235 valores com significado.
- **F9** — oito regras de negócio só existiam no SQL de `consumption`: a conversão pelos carrinhos
  fechados, a aprovação por tentativa, o reembolso sobre o capturado do mês inteiro, entre outras. O
  `nl_sql` só reproduziu os 23 gabaritos depois de escrevê-las em forma estruturada.

Ao desenhar a resposta, duas evidências mostraram que o texto à mão não basta:

- **F22** — o `gateway_response_code` é sorteado sem relação com o resultado: o `51`, saldo
  insuficiente pela convenção do mercado, aparece em 520 autorizações aprovadas. Um significado
  escrito pela convenção seria falso.
- **F23** — as tabelas das Perguntas de Negócio citam medidas e fatos que não são os das views, e o
  pacote de metadados as publica em `questions`. A P08, por exemplo, aponta `fact_purchase_order_item`
  para o CMV.

A Q3-a fixou a direção: declarativo no dbt, com o significado no `meta` da coluna e as métricas
estruturadas no glossário, com teste contra a view. As Q15 a Q18 fixaram a forma. O desenho passou
por três rodadas de revisão (`codex1_bloco5_desenho_r1.md` a `r3.md`). As sondas do mecanismo foram
medidas antes desta decisão (`tests/test_dominios_de_valores.py` e um `dbt parse` numa cópia do
projeto).

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **Catálogo único de domínios e de métricas, derivado na coluna e nos documentos** (a escolhida) | Cada significado e cada regra são escritos uma vez; o resto é derivado e conferido, no padrão que o projeto já usa para `sensitivity` e `description`; o significado chega ao pacote pelo `meta`, sem mudar o esquema | O escritor de `.yml` cresce: passa a escrever mapa e teste, não só escalar; os documentos ganham trechos gerados; o montador das métricas é código a manter |
| Mapa de valores escrito em cada coluna | Lê-se onde está | O estado do pedido se repetiria em seis colunas de quatro fatos, e a guarda de igualdade não evita a manutenção dupla |
| Significado na origem (SQLAlchemy), herdado por transporte | O mesmo mecanismo da descrição | Não alcança as colunas que o legado mapeia por `case`, que calculam: boa parte das fatos ficaria sem significado |
| Camada semântica do dbt (MetricFlow) | Ferramenta padrão para métricas | Componente novo na arquitetura, com custo e contrapartida no GCP; a Q3 não a escolheu |
| Métricas só em prosa estruturada | Barato | Não prova que a definição sozinha reproduz o número: a lacuna do F9 continuaria invisível |

## Decisão

Os domínios de valores e as métricas são **declarados uma vez**, em dois catálogos do glossário, e
**derivados** em todo lugar onde aparecem. O derivado é conferido por teste e pelo `make check`, nunca
editado à mão.

**Os domínios** (`docs/glossario_de_negocio/dominios.yml`). Cada domínio tem nome em inglês, descrição
e o mapa valor → significado, em português. Cada significado traz a fonte: valor sem fonte é pergunta
ao Owner, nunca texto escrito por dedução. O catálogo também declara os membros desconhecidos de cada
dimensão e as regras de exclusão da cobertura, cada uma com o motivo.

A coluna de `analytics` ou de `consumption` aponta para o domínio no próprio `.yml`, com
`meta.value_domain`, e pode trazer:

- `null_meaning` — sem ele, a coluna ganha `not_null`, porque o `accepted_values` não decide a
  nulidade;
- `impossible` e `not_observed` — por coluna, cada valor com o motivo.

O `make catalog` deriva na coluna duas coisas:

- o `meta.values`, que é o mapa menos os valores impossíveis;
- o `accepted_values`, com exatamente esses valores e marcado por `config.meta.value_domain`.

O escritor de linhas de `models/` substitui essas subárvores por inteiro e escreve as chaves entre
aspas duplas: o `00` continua texto. Ele recusa a forma em linha, como já fazia. Medido: o `dbt parse`
aceita o resultado, e o `meta.values` e o teste chegam ao *manifest* como texto.

**As métricas** (`docs/glossario_de_negocio/metricas.yml`). O catálogo tem cinco seções: fontes
(relação, junções e a data que define o período), filtros nomeados, medidas, métricas e views. Para
cada view ele declara o grão, o grão de agregação de cada fonte, a combinação das fontes e o papel de
cada coluna.

Um **montador fixo** gera o SQL só a partir dessa declaração. Para cada fonte, ele seleciona o grão da
fonte e as medidas, aplica os filtros e agrupa pelo grão. Depois combina as fontes pela regra declarada
e calcula as métricas por cima. O resultado é comparado com a view auditada, linha a linha. Os exemplos
que o formato tem de reproduzir são três:

- **P07** — a razão simples;
- **P08** — a composição entre duas fatos;
- **P10** — o denominador com grão mais curto.

O que não cabe nessa forma aponta, com `reference:`, para o teste do Bloco 1b que confere aquela coluna.
O resultado sai em dois números que não se somam: o que a declaração reproduziu e o que a referência
conferiu.

O `metricas.yml` é o dono da fórmula, do filtro, da data e do grão. A regra de cada conceito e a tabela
de cada pergunta passam a ser **trechos gerados** nos `.md` do glossário. O texto curto que vai ao
BigQuery continua sendo o começo do bloco `docs`, e o porquê continua em prosa, à mão.

## Consequências

- **Positivas:**
  - o significado de cada valor e a regra de cada métrica chegam aos três consumidores pela mesma
    fonte: o pacote, o `meta` e o texto do dbt;
  - a cobertura é um oráculo: "N de N colunas classificadas" e "N de N medidas reproduzidas";
  - deriva como a do F23 passa a falhar o `make check`.
- **Negativas:**
  - o escritor de `.yml` e o gerador de trechos crescem, e cada forma nova que eles aceitam é superfície
    a testar;
  - o `make catalog` passa a escrever teste do dbt, e a sequência de publicação ganha o
    `make catalog-derivados` antes do *build*;
  - a comparação com a view prova que a declaração e a view dizem o mesmo, não que ambas leram certo a
    regra — a independência continua sendo a das referências do Bloco 1b;
  - o `metricas.yml` é declaração extensa, que o Owner revisa por inteiro.
- **Paridade com o GCP:**
  - o `meta.values` e o `accepted_values` são `.yml` do dbt e valem igual no BigQuery: o `persist_docs`
    leva a descrição, e o teste roda no adaptador;
  - o montador gera SQL portável sobre `analytics`, e no BigQuery rodaria pelo mesmo cliente das
    referências;
  - os trechos gerados mudam o texto que vai ao BigQuery pelo mesmo caminho do F4;
  - nada disso foi aplicado no GCP nesta fase (Q14).
- **Documentos a atualizar:**
  - [README do glossário](../glossario_de_negocio/README.md): a convenção dos dois catálogos e dos
    trechos gerados;
  - [Governança de Dados](../governanca_de_dados.md) §5.1: as chaves novas de `meta`;
  - [Pacote de Metadados](../pacote_de_metadados.md), o esquema e o exemplo: os campos `metrics` e
    `filters`, e o `meta` novo;
  - [Consumidores](../consumidores.md) §5: a `prevista` antes e a `feita` depois;
  - [Execução Local](../execucao_local.md): o `make catalog-derivados`;
  - o [plano da base dos consumidores](../../PLANO_base_dos_consumidores.md), onde está o desenho.
