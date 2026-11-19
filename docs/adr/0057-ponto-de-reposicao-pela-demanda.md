# ADR-0057 — Derivar o ponto de reposição da demanda de cada par, com uma regra só para a P12 e o alerta

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 18/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | D94 ([Pendências](../pendencias.md)), aberta pelo [F36](../achados_nl_sql.md#f36--o-ponto-de-reposição-fixo-deixa-de-distinguir-com-o-estoque-da-v5--gravidade-média) |
| Substitui / é substituída por | — |

## Contexto

A P12 (`consumption.skus_below_reorder_point`) lista os pares armazém/SKU com o disponível abaixo do ponto de
reposição. O ponto é **fixo, 25 unidades para todo par**: a variável `reorder_point_units` do dbt, espelho de
`alerta.limiar_de_unidades` do `streaming/fluxo.yml`, que é o dono do valor e o limiar do alerta de estoque baixo
do Beam. O próprio `fluxo.yml` justificava o número único: a origem não tem ponto de reposição, e inventá-lo
"exigiria um ADR que ninguém pediu".

A V5 da reabertura passou a dimensionar a compra e a abertura do estoque pela venda, e a venda é esparsa. Depois do
ciclo de 18/11/2026, **2.868 dos 3.046 pares (94%)** ficaram abaixo dos 25, e 410 em ruptura. A P12 passou a
responder "quase tudo". O dado é coerente com a regra. Foi a regra que não acompanhou a V5 (**F36**).

Medido no armazém em 18/11/2026, só leitura, sobre o estado da `v2.2.0`, para escolher a regra:

- **Prazo de reposição.** A origem não tem coluna de *lead time*. O prazo real, do pedido ao primeiro
  recebimento (`analytics.fact_purchase_order_item`), tem mediana de **28 dias** nos 1.116 itens do varejo, com
  p10 de 6 e p90 de 53 dias. Por fornecedor, as medianas vão de 11 a 48 dias, em 30 fornecedores. O prometido
  (`expected_at − ordered_at`) tem mediana de 26 dias.
- **Demanda.** Só 578 dos ~3.047 pares venderam nos 90 dias da janela de cobertura (`cover_window_days`). No ano,
  a venda mediana dos pares que venderam é de 3 unidades, com p90 de 5 e máximo de 11.
- **Demanda censurada.** Par em ruptura não vende. Das 410 rupturas, 341 não tiveram venda nos 90 dias, e um
  ponto calculado nessa janela seria zero justamente para elas.

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **Ponto = teto(demanda diária × (prazo + margem)), com prazo e margem em dias** (a escolhida) | A fórmula clássica: a demanda esperada no prazo de reposição, mais uma folga; fácil de auditar e de declarar no glossário; acompanha a demanda de cada par | Com venda esparsa, o ponto fica em 0, 1 ou 2 unidades (ver Consequências) |
| Margem estatística, `z·σ·√prazo` | A fórmula de livro para nível de serviço | Com 3 unidades por ano, o σ é ruído: o ponto oscila sem motivo, e a regra fica mais difícil de explicar sem ganho medido |
| Ponto fixo menor (por exemplo, 2) | Custo quase nulo | O defeito volta quando o perfil do dado mudar; a regra continua sem relação com a demanda |
| Mínimo e máximo por classe ABC de giro | Prática comum de varejo | Cria uma classificação nova, com regra, glossário e testes próprios, para um ganho pequeno neste dado |
| **Prazo único, declarado, 28 dias** (a escolhida) | Um número com a origem da medida escrita; o mesmo para a P12 e o alerta; não muda com a regeneração | Ignora a diferença entre fornecedores |
| Prazo por fornecedor, medido do dado | Mais realista | O SKU pode ter vários fornecedores, e a regra precisaria escolher um; o prazo mudaria a cada regeneração; o *streaming* herdaria a escolha |
| Prazo prometido (`expected_at`) | Está na origem | É a promessa, não o realizado: o p90 real, de 53 dias, passa dela, e o ponto subestimaria a necessidade |
| **Janela própria de 365 dias para a demanda do ponto** (a escolhida) | Atravessa a ruptura: o par que vendeu no ano e está zerado continua com ponto positivo | Uma variável a mais; o ponto reage devagar a uma mudança de demanda |
| A janela da cobertura, 90 dias | Uma variável só | A ruptura longa some da P12 justamente quando mais precisa de reposição: ~158 pares, sem 341 rupturas |
| 90 dias com piso de 1 unidade | Toda ruptura entra | Inclui 30 pares que nunca venderam; mistura "precisa repor" com "está zerado": ~499 pares |
| **O *streaming* lê o ponto de cada par do armazém** (a escolhida) | Uma regra, um dono (o dbt); o alerta e a P12 concordam por construção; usa o caminho que a semeadura do saldo já tem | O ponto fica fixo durante a execução do Beam; refazer a prova do *streaming* ao vivo |
| O *streaming* mantém os 25 fixos | Nenhuma mudança no Beam | A P12 e o alerta passam a discordar sobre o que é estoque baixo: defeito novo, só que conhecido |
| O Beam calcula a demanda sozinho | Independente do armazém | Duas implementações da mesma regra, que podem divergir (`CLAUDE.md` §5: o que se revisa é a declaração) |

## Decisão

O ponto de reposição passa a ser **derivado da demanda de cada par**, por uma regra só, declarada no dbt e lida pela
P12 e pelo alerta do *streaming*:

```
ponto de reposição = teto( venda dos últimos 365 dias ÷ 365 × (prazo de reposição + margem de segurança) )
prazo de reposição = 28 dias   (a mediana medida do pedido ao primeiro recebimento, 18/11/2026)
margem de segurança = 14 dias  (metade do prazo)
```

- **A venda** é a saída por venda (`is_sale`) do par, na mesma definição da demanda da cobertura. Transferência,
  ajuste e devolução ao fornecedor não são demanda.
- **O par entra na P12** quando o disponível fica **abaixo** do ponto (`<`), como hoje. O par sem venda no ano
  tem ponto zero, e só entraria com disponível negativo.
- **O ponto vem do lado frio.** Ele é calculado sobre a fato de movimento, ancorado no último movimento dela, e
  publicado por um modelo dbt no grão do par (origem, armazém, SKU). A P12 o lê em vez da constante, e mantém o
  saldo de agora, frio mais quente, como hoje. Quem não está no modelo, por exemplo um par visto só pelo fluxo,
  tem ponto zero.
- **O alerta do *streaming*** lê o ponto de cada par do armazém ao subir o *pipeline*, pelo mesmo caminho da
  semeadura do saldo, e o mantém fixo durante a execução. A travessia continua a mesma: abre ao cruzar o ponto
  para baixo e normaliza ao voltar.
- **O dono muda.** Prazo, margem e janela passam a ser variáveis do dbt (`dbt_project.yml`), com a origem da
  medida no comentário. Saem a `reorder_point_units` e o `alerta.limiar_de_unidades`, e com eles o espelho e o
  teste que conferia os dois.
- **Fora do alcance.** A posição de estoque do livro-texto soma o que está pedido e não chegou
  (`quantity_outstanding`). A P12 pergunta quem está abaixo do ponto **agora**, não quanto pedir, e continua
  comparando o disponível. Passar à posição seria outra decisão.

Nome do modelo, nomes das variáveis, testes e a prova no ciclo ficam no plano da fase, que passa pela revisão por
outro agente antes de executar.

## Consequências

- **Positivas:**
  - a P12 volta a separar: medido em leitura, **~213 pares (7%)** contra 2.868 (94%) com o ponto fixo. Todas as
    rupturas com venda no ano entram;
  - a P12 e o alerta passam a ter, por construção, a mesma definição de estoque baixo;
  - o ponto passa a ser uma coluna com regra declarada no glossário, e não uma constante sem origem;
  - a regra acompanha o dado: se a demanda engrossar, o ponto sobe sozinho.
- **Negativas:**
  - **com este dado, "abaixo do ponto" coincide com "ruptura".** O ponto calculado é 0 para 1.387 pares, 1 para
    1.637 e 2 para 23. Os ~213 pares abaixo dele são, todos, os que estão zerados e venderam no ano. A faixa
    "baixo, mas ainda com estoque" fica vazia por causa da venda esparsa, não da regra. A P12 passa a separar,
    mas não antecipa a ruptura;
  - o ponto atrasa uma execução do dbt: a venda que chega pelo caminho quente muda o saldo na hora, mas só muda o
    ponto quando a fato a absorver. Uma subida do Beam também o congela até a próxima;
  - um prazo único ignora a diferença entre fornecedores (de 11 a 48 dias de mediana);
  - muda uma regra de negócio publicada: os consumidores recebem o antes → depois da P12 e do alerta, e a prova do
    *streaming* ao vivo precisa ser refeita, com o custo de memória da troca de ambiente (R11);
  - os números acima são medida de leitura sobre a `v2.2.0`, e não o resultado da view: o ciclo da fase remede
    (**P5**).
- **Paridade com o GCP:**
  - o modelo do ponto é um modelo dbt como os outros, materializado no BigQuery pelo mesmo projeto;
  - o `nuvem.Semear` do Dataflow, que já lê o saldo do BigQuery, passa a ler também o ponto de cada par, como
    entrada do *setup*. Nada disso é exercitado nesta fase: o GCP está desmontado (L9).
- **Documentos a atualizar** (com a implementação, na fase do F36):
  - o glossário de negócio: [cobertura de estoque](../glossario_de_negocio/cobertura_de_estoque.md),
    [ruptura de estoque](../glossario_de_negocio/ruptura_de_estoque.md) e
    [perguntas de negócio](../glossario_de_negocio/perguntas_de_negocio.md), com a regra do ponto; o
    `metricas.yml`, com a coluna `reorder_point` e a referência da auditoria;
  - o `.yml` da camada `consumption`, a descrição de `reorder_point`;
  - [Streaming](../streaming.md): o limiar por par, lido do armazém;
  - [Qualidade de Dados](../qualidade_de_dados.md): o teste do espelho que sai e o que o substitui;
  - [Consumidores](../consumidores.md) §5: a `prevista` da P12 antes, a `feita` depois, com o antes → depois
    medido;
  - [Achados](../achados_nl_sql.md): o F36, com o que foi feito.
