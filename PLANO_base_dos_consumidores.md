# Plano — a base dos consumidores: `gdados`, `nl_sql` e `bi-como-codigo`

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 13/11/2026; rodada 1 de perguntas respondida no mesmo dia (§6); **revisão fechada** na rodada 3, sem achado aberto (§9); **emendado** no mesmo dia com o que a leitura dos planos dos consumidores acrescentou (§2.1), o que abriu a rodada 3 de perguntas, **respondida** pelas recomendações (Q9 a Q11, §6); a emenda teve a rodada 4 de revisão (um bloqueante e três ajustes, aceitos e respondidos no §9), e a rodada 5 a **fechou sem achado**; **Bloco 0 entregue** em 13/11/2026 (§3); **alinhamento central** das pendências dos três consumidores em 14/11/2026 (§2.2), com a rodada 4 de perguntas respondida (Q12 a Q14, §6) e o **Bloco 0b entregue** (§3); **Bloco 1 entregue** em 14/11/2026, com a Q8 respondida e o ADR-0052 (§3); próximo: a revisão do Bloco 1 e o Bloco 1b |
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
fechamento desta fase não declara os consumidores livres dela (RVC-1-09). **Pela Q10-a, a D66 entra
nesta fase**: é perguntada antes do Bloco 4 (§8), e o que está acima vale até a resposta.

### 2.1 O que a leitura dos consumidores acrescenta (emenda de 13/11/2026)

O inventário acima nasceu dos achados que voltaram para cá. Lidos os planos dos três consumidores
(`gdados/PLANO.md` e `docs/decisoes.md`, `bi-como-codigo/PLAN.md` §3.5, §6.2 e §7,
`nl_sql/CLAUDE.md` §3 e §4), em 13/11/2026 e só por leitura, sobram nove lacunas que o plano não
tratava. **Esta fase não completa os consumidores**, porque cada um termina na sessão dele. Ela completa
o que eles leem daqui, e cada lacuna abaixo tem um destino.

| # | Lacuna | Consumidor | Evidência | Destino |
|---|---|---|---|---|
| L1 | O canal de volta está quebrado: a regra 1 manda escrever os achados em `~/Projetos/mvp_eng_dados_1/docs/achados_nl_sql.md`, arquivo que saiu de lá em 13/11 | N | `nl_sql/CLAUDE.md` §3, regra 1, e a tabela de arquivos | Bloco 0, aviso — o primeiro a sair |
| L2 | A D03 do `gdados` ainda lista como alternativa o anexo de *release* com *hash*, que a D91 daqui descartou, e não sabe da decisão | G | `gdados/docs/decisoes.md`, D03; D91 nas Pendências §2 | Bloco 0, aviso |
| L3 | Não há caminho para achado novo durante a fase: os próximos passos do `nl_sql` (grão e colunas, regras globais, data local de `date_key`, membros "desconhecido") vão gerar F11 em diante, e o inventário para em F10 | N, G, B | `nl_sql/CLAUDE.md` §4, "Próximos passos" | Bloco 0, item 3: a regra de entrada |
| L4 | A página de estrutura e ambientes do portal (infraestrutura local, Terraform, mapa de paridade, batch e *streaming*, diagramas entidade-relacionamento) não tem fonte declarada: a D91 leva metadados de dados e nada disso | G | `gdados/PLANO.md` §3 | Bloco 4, no contrato do pacote |
| L5 | Nada prova qual *commit* construiu o armazém que o BI lê: a procedência da D91 é a dos artefatos do dbt, não a do banco | B, G | `bi-como-codigo/PLAN.md` §3.5, linha "Version": "has no evidence today" | Bloco 4, diagnóstico e proposta; se pedir objeto novo no armazém, volta ao Owner |
| L6 | Só duas das 16 views são examinadas (F1 e F2), e por achado externo, não por auditoria. A etapa 2.11 do BI exige auditar cada view (não aditividade, saldo dependente do tempo, população recortada). A verificação do Bloco 5 confere a métrica contra a própria view e não acharia defeito nela. Não conferido: se alguma auditoria anterior cobriu as outras 14 | B, G | `bi-como-codigo/PLAN.md` §6.2, etapa 2.11 | **Q9-a**: Bloco 1b |
| L7 | A D66 fica fora, e a primeira publicação do BI leva o relatório da P13, que ela recorta | B, G | D66 nas Pendências; `bi-como-codigo/PLAN.md` §6.3 item 3 e N43 | **Q10-a**: pergunta própria antes do Bloco 4 |
| L8 | Dois portais para a mesma governança: a etapa 2.7 do BI ("reading portal of the data governance") e o `gdados`, sem decisão sobre se são duas coisas nem se leem a mesma fonte | G, B | `bi-como-codigo/PLAN.md` §6.2, 2.7; `gdados/PLANO.md` §1 | **Q11-a**: um contrato; a pergunta vai no aviso do Bloco 0 |
| L9 | O efeito no BigQuery fica sem medição: o F4 e o F10 só se provam no PostgreSQL, e o GCP está desmontado. Para o `nl_sql`, o que importa é o que o Gemini lê no BigQuery | N | Blocos 3 e 6; D92 | Fechamento: limitação declarada |

A retenção foi examinada e **não é lacuna**: está declarada por objeto (Governança §8,
`meta.retention`, `tests/test_retencao.py`), e o pacote da D91 leva o `meta`. O item 8 da V3 é a
expiração dos *datasets* do BigQuery, fora desta fase como o resto da V3.

### 2.2 O alinhamento central (14/11/2026)

O Owner pediu às três sessões um arquivo com as pendências que envolvem outro projeto
(`gdados/docs/alinhamento_entre_projetos.md`, `bi-como-codigo/docs/upstream_questions.md`,
`nl_sql/PENDENCIAS.md`) e pediu a esta sessão que as respondesse de forma central. O que é comum
ficou aqui; o que é de um projeto só foi autorizado para a sessão dele. As respostas estão nos avisos de
14/11/2026 (`data/medicoes/base_consumidores/avisos/`, fora do Git), que apontam para os *commits*
daqui. Entraram no plano, pela regra de entrada (Bloco 0, item 3):

| # | Item | Consumidor | Evidência | Destino |
|---|---|---|---|---|
| F8+ | Além do grão: `dim_brand`, `dim_category` e `dim_payment_method` não têm descrição de tabela | N, G | Achados, F8; *manifest* de 13/11/2026 | Bloco 3, com o F8 |
| F11 | A descrição de `fact_payment_transaction` cita "a pergunta P09" | N | `_analytics__models.yml:1069` | Bloco 3 |
| F12 | Nada diz para agrupar pelo nome quando o mesmo membro conformado existe nas duas origens, nem que o código de SKU e de cliente se repete entre origens para entidades diferentes | N, G, B | Achados, F12 | Bloco 3, na descrição de cada dimensão conformada. A auditoria do Bloco 1b confere se alguma view agrupa pela chave |
| F13 | `fact_shipment_item.date_key` é `coalesce(shipped_at, source_created_at)`, e a descrição diz "despacho": 346 das 7.556 linhas são de remessas não despachadas, **conferido aqui** no armazém local em 14/11/2026 | N, G, B | `fact_shipment_item.sql:131`; `_analytics__models.yml:1761` | Bloco 3, a descrição. Separar as duas datas é modelagem e só vira pergunta se a auditoria do Bloco 1b achar uma view que conte despacho por essa data |
| L10 | As evidências coletadas no GCP antes do desmonte estão só no `mvp_eng_dados_1`, fora do Git e fora da D91 | G | `gdados/docs/verificacao_de_viabilidade.md` §7.5; `mvp_eng_dados_1/data/medicoes/etapa_13/evidencias/` | Bloco 4, com a L4: o que entra e sanitizado como. Até lá, `not_available` no pacote |
| L11 | Os consumidores não tinham canal de saída daqui, nem regra para pedir o banco ou uma janela de leitura, nem registro das mudanças de valor (UQ-03 a UQ-07 do BI, O7 do `gdados`) | G, B | Os arquivos de pendências dos dois | Bloco 0b: [Consumidores](docs/consumidores.md) |
| L12 | O `gdados` (E1) e a 2.7 do BI precisam do formato do pacote para começar, e o Bloco 4 não tem data | G, B | `gdados/docs/decisoes.md`, D03 (A5); UQ-09 do BI | **Q13**: Bloco 0b, a especificação |
| F14 | Duas descrições de `fact_refund` erradas: `refunded_at` está preenchido também nos 8 solicitados e nos 2 recusados (**conferido aqui**, 14/11/2026), e `originally_captured_amount` é o capturado da transação revertida | N, G, B | `_analytics__models.yml:1318` e `:1337`; `fact_refund.sql:32` e `:40` | Bloco 3. Anular `refunded_at` fora do concluído seria mudança de dado, e só vira pergunta se a auditoria do Bloco 1b achar uma view que conte reembolso concluído por essa data |
| F15 | Descrições que apontam para o que não está na `analytics` (`order_status_history`, seções de documento, invariantes, ADRs) | N, G | `_analytics__models.yml:667`, `:1878`, `:2105` e outras | Bloco 3: a regra no lugar da referência, no texto que vai ao BigQuery (o curto do F4) |
| F16 | "Data de referência do armazém" ambígua com `dim_warehouse` | N, G | `_analytics__models.yml:185` e outras sete | Bloco 3 |
| L13 | O custo real da fase GCP entraria só no `mvp_eng_dados_1`, e os portais leem daqui (H2 do `gdados`) | G | `gdados/docs/alinhamento_entre_projetos.md` §4 | Em 16/11/2026, o custo entra também aqui, no mesmo dia ([Consumidores §7](docs/consumidores.md#7-o-gcp)) |

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
   canal de volta muda: a regra 2 do `CLAUDE.md` de lá proíbe reimportar. O aviso dele sai
   **primeiro**, porque o canal está quebrado agora (L1). O do `gdados` leva a D91 decidida, para a
   D03 de lá (L2). O do `gdados` e o do BI levam a pergunta da Q11-a, de quantos portais existem e
   se os dois leem o mesmo pacote, para cada sessão decidir (L8).
3. **A regra de entrada de achado novo** (L3): todo achado que chegar durante a fase — do `nl_sql`
   pelos Achados ou do BI pela auditoria da 2.11 — ganha um ID (F11 em diante) no dono dele, os Achados,
   e uma linha no §2 deste plano com o bloco de destino. Defeito de número ou texto já lido entra no
   bloco aberto mais próximo; o que pede decisão vira pergunta da rodada seguinte; o que chegar depois
   do Bloco 4 entra no pacote como campo novo, sem quebrar. O que não couber nesta fase vai às
   Pendências no fechamento, com o motivo.

**Entregue em 13/11/2026**, com a autorização do Owner:

- item 1 em `e63f1cb`;
- item 2: a Q1 na D92 (`040a796`); os três avisos fora do Git, em
  `data/medicoes/base_consumidores/avisos/` (`aviso_nl_sql.md`, `aviso_gdados.md`,
  `aviso_bi_como_codigo.md`), para o Owner levar a cada sessão. O número da D66 citado no aviso do BI
  é o do dado da v1.1.0 (16 remessas, de 04/11), não o 12 da v1.0.0 que aparece na Q10;
- item 3: a regra de entrada vale a partir daqui.

O que cada consumidor fará com o aviso é da sessão dele, e esta fase não o acompanha.

### Bloco 0b — o canal e o formato (Q13, L11, L12)

**Entregue em 14/11/2026**, revisado por outro agente antes do *commit* (§9):

- [Consumidores](docs/consumidores.md): quem lê, as regras de leitura, o banco compartilhado e a janela
  de leitura, os canais, o registro do que mudou para quem consome e os *commits* marcados para fixar;
- [Pacote de Metadados](docs/pacote_de_metadados.md): o formato 1, com o esquema e um exemplo
  copiado do *manifest* real, guardados por `tests/test_pacote_de_metadados.py` (o exemplo passa no
  esquema; vinte e uma alterações dele são recusadas, e uma auditoria completa passa). O Bloco 4 **gera** conforme este formato e não o
  redesenha. O que fica para ele está na §5 do documento.

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

**Entregue em 14/11/2026** (medições em `data/medicoes/base_consumidores/bloco1/`, fora do Git; cada
mudança em [Consumidores §5](docs/consumidores.md#5-o-que-mudou-para-quem-consome)):

- **F1** em `9aeea8d`: o denominador soma as origens do canal pelo nome. Jan/2024, Conta, Aplicativo:
  4,5455 → 4,3478. Teste de unidade e reconciliação `p15_…` com as fatos (*tag* `fronteira`), os dois
  com contraprova sobre o SQL anterior (a reconciliação acusa 23 pares mês × canal nele).
- **F3** em `d212c07`: a causa medida é regra vigente, não defeito. Os 15 pedidos realizados do legado
  que a dimensão conta e a fato não tem estão todos sem item aceito, com os itens na quarentena (D35,
  ADR-0038). Com eles, a dimensão e a fato batem nos 1.574 clientes. O teste
  `cliente_reconcilia_com_a_fato_de_vendas` guarda a regra com a exceção declarada (sem ela, acusa os 15
  clientes), e as descrições dizem o recorte. Se a regra deve mudar é a **Q7**, que tem o mesmo padrão
  da D66 (pai aceito, filhos todos rejeitados) e vai com ela. Na DAG, a tarefa de quarentena passou a
  deixar os testes `fronteira` para o fim.
- **F2**: diagnóstico e proposta em `bloco1/f2_diagnostico_e_proposta.md`; a **Q8** foi respondida pelas
  recomendações e registrada no [ADR-0052](docs/adr/0052-giro-pelo-estoque-medio-do-trimestre.md)
  (`3010ead`, com o aviso `prevista` ao BI); a view em `69ea446`. Antes e depois: 6.990 linhas e o mesmo
  CMV, 1.449 giros mudam mais de 10%, e os indefinidos vão de 620 a 1.216, 1.212 deles com uma
  correção-relâmpago do gerador no trimestre (medido na revisão, RVL1-1-05), registrada como [V4](docs/pendencias.md#v4--a-correção-relâmpago-do-gerador-de-estoque-registrada-em-14112026).
  A primeira versão levava mais de 2 minutos por leitura. A final lê em 6 s: a grade só dos trimestres
  com venda, montada por `union all`. Da revisão (§9, rodadas 9 a 11): o dia com posição e sem custo
  conhecido torna o valor médio e o giro indefinidos, em vez de média parcial (um par-trimestre hoje;
  a regra está no glossário e na descrição da view, e o ADR-0052 fica como foi aceito). As correções-
  relâmpago são 1.851 pelo `source_id` (1.792 no retail, 59 no legado), e não as 1.514 da primeira
  contagem, que pedia uma saída da mesma quantidade em até 5 minutos. Saídas literais em
  `bloco1/rvl1_saidas.md`.
- **Nos Achados:** a nota de replicação do F1, F2 e F3 entrou em `77e1182`, depois do *commit* das
  entradas F14 a F16 do `nl_sql` (`0edfd1e`), que o Owner aprovou.

### Bloco 1b — a auditoria das 16 views (Q9-a)

Depois do F1 e do F2, as 16 views de `consumption` passam pelos três critérios da etapa 2.11 do BI:
não aditividade, saldo que depende do tempo e população recortada. São três passos, por view.

1. **A definição primeiro** (RVC-4-03). A referência nasce do glossário e do ADR da pergunta,
   **nunca** do SQL da view. Por isso, antes de escrevê-la, confere-se que a definição está completa
   no texto. Onde falta, o texto vem antes: a regra do pedido realizado do F5 sai aqui, e não no
   Bloco 3; as regras do F9 que a view usa saem aqui em prosa, no glossário (a população de
   autorizações da P09, o capturado do mês inteiro do reembolso, os outros itens do F9). Escolha nova
   é pergunta ao Owner, nunca leitura do SQL. A forma estruturada e o ADR dela ficam no Bloco 5.
2. **A referência, com as fontes que a pergunta declara** (RVC-4-02). Cada pergunta diz de onde lê.
   Em geral é `analytics`. A **P12** soma à fato os deltas do caminho quente
   (`raw.inventory_movements_stream`, com a fronteira pela ausência do `movement_id` na fato,
   Streaming §4.1) e as reservas de `trusted.inventory_balances`. Tudo é lido num corte consistente,
   numa transação `REPEATABLE READ`. O critério de **população** compara a view com a população
   elegível na camada responsável, por exemplo a P13 com as remessas entregues de `trusted.shipments`,
   porque recalcular sobre a fato conservaria o que ela perdeu. Onde isso não é possível, o limite
   fica escrito. As referências são testes do custodiante, que já lê as camadas internas. O login do
   BI não muda.
3. **A contraprova** (RVC-4-04). Uma referência que só concorda com a view corrigida não prova que
   acharia o defeito. Para o F1 e o F2, o SQL da versão defeituosa (do *commit* anterior à correção,
   compilado) roda como **consulta somente leitura**, sem criar objeto. A referência tem de acusar a
   diferença nos casos de antes do Bloco 1 (o 4,5455 do F1, por exemplo) e passar com a view
   corrigida. Os casos e os testes do Bloco 1 são os mesmos, aqui ligados à referência.

A conclusão da **P13** espera a D66 (seção seguinte). Se a D66 trouxer fato nova, a auditoria da P13
é refeita sobre ela antes que o Bloco 5 a use como referência.

- Defeito achado vira F novo pela regra de entrada (Bloco 0, item 3). Correção sem decisão entra
  neste bloco; o que pede regra vira pergunta.
- View sem defeito ganha o resultado escrito: "auditada em `<commit>`, critérios, cálculo de
  referência". Esse resultado vai nos Achados, no pacote (Bloco 4) e no fechamento.
- Os cálculos de referência ficam versionados e rodam como teste. São o modelo da verificação do
  Bloco 5, que também deixa de comparar a métrica com a própria view.
- O efeito no BI é o mesmo do F1: o esquema não muda, os valores mudam, e o aviso diz quais.

**Entregue em 14/11/2026** (medições em `data/medicoes/base_consumidores/bloco1b/`, fora do Git):

- **Passo 1, a definição:** a regra do pedido realizado na receita líquida (F5); a fórmula da conversão,
  que dizia `cart_count` no denominador quando o texto ao lado tirava os abertos; e o "como se conta" da
  P09, da P10 e da P15 nas Perguntas de Negócio (F9). Nenhuma escolha nova.
- **Passo 2, a referência:** uma por view em `tests/auditoria/`, comparada com a view linha a linha
  (`except all` nos dois sentidos) num corte `REPEATABLE READ READ ONLY`; e oito conferências de
  população contra `trusted` em `tests/auditoria/populacao/` (a da P13 é o teste dbt do bloco da D66).
  **Limite declarado:** o autor das referências leu o SQL das views antes (o passo 1 tirou de lá o F9);
  a independência é de construção e de fonte, não de autoria. Nas da P05, P07, P13 e P14 a construção
  é quase a da view, e o critério de população delas fica com as conferências contra `trusted`
  (RVB1b-1-05).
- **Passo 3, a contraprova:** o SQL compilado das versões defeituosas do F1, do F2, da P04 e da P14, em
  `tests/auditoria/contraprova/`, roda como consulta somente leitura, e a referência tem de discordar
  dele. Uma mutação na referência da P02 (sem o filtro de pedido realizado) fez o teste acusar 271
  linhas.
- **O que achou** (F17 a F20 nos Achados): a P14 e a P04 perdiam o pedido de itens rejeitados em
  cascata, o padrão da D66 (13 pedidos; 1 estreia a menos e 6 em mês mais tarde). O Owner decidiu aplicar a mesma regra, e
  as duas foram corrigidas em `12677a3`. Duas observações sem efeito nos números: 14 carrinhos
  convertidos sem item no dado sintético (P07) e o ranking da P03, que se partiria se um produto mudasse
  de atributo (hoje, nenhum). A não aditividade da P16 entre categorias já estava declarada. A P12 usa o
  reservado da projeção, que diverge das reservas ativas em 97 pares, sempre para baixo, como a
  invariante 8 prevê.
- **O resultado:** as 16 views auditadas em `12677a3`, em `tests/auditoria/resultado.yml`, que é a
  declaração de que o pacote tira o `view_audits`. `tests/test_auditoria_das_views.py`: 29 testes (as 16
  referências, as 8 populações, as 4 contraprovas e a cobertura).

### D66 — antes do Bloco 4 (Q10-a)

**Respondida em 14/11/2026: (a), uma fato no grão da remessa**, a recomendada. Remedida antes da
pergunta, no armazém de `d212c07`: 147 remessas do legado entregues em `trusted.shipments`, 131 na fato,
**16 de fora** (10,9%), todas com os itens na quarentena e nenhum item aceito; o retail fecha 3.166 de
3.166. Vira o **Bloco D66**, com ADR, logo depois do Bloco 1b e antes do Bloco 2, porque a P13 conclui a
auditoria sobre ela e o BI fixa o commit dela (N85 de lá).

**Bloco D66 entregue em 14/11/2026, antes do 1b** (a auditoria da P13 precisa dele, e o resto do 1b
não depende dele), em `745fe6a`, pelo [ADR-0053](docs/adr/0053-fato-no-grao-da-remessa.md):
`fact_shipment`, uma linha por remessa (3.772 no armazém local), reconciliada com `trusted.shipments`;
a P13 lê dela e conta as 16 (3.297 → 3.313 remessas entregues no total); o teste
`p13_conta_toda_remessa_entregue` compara a view com a população de `trusted`, e a contraprova sobre a
view anterior acusa 16 remessas em 12 meses. A P14 continua na fato de item; se ela tem o mesmo recorte
é pergunta da auditoria do 1b.

A D66 é perguntada com as alternativas dela (Pendências) e com o que já foi medido: o M27 do BI e a
medição posterior à regeneração que a própria D66 registra. As duas são históricas e são remedidas
antes de perguntar. A auditoria da P13 no Bloco 1b só conclui depois da resposta (RVC-4-02). Se a
resposta for a fato no grão da remessa (ADR-0033), ela vira bloco próprio, com ADR, antes do Bloco 5,
e o pacote leva a limitação até lá. Se a definição mudar, o glossário e a descrição da view mudam no
Bloco 3 ou num *commit* próprio.

### Bloco 2 — os testes que faltam (F6)

Os sete `relationships` em `_analytics__models.yml`, de 44 para 51. Sem decisão: é a mesma regra das
outras. Os órfãos são medidos aqui antes, no armazém local.

**Entregue em 14/11/2026.** Medidos antes, no armazém local: 0 órfãos nas sete, todas preenchidas
(`fact_sales_order_item.brand_key` 7.738 linhas; `fact_refund` 120 em cada uma das três;
`fact_payment_transaction.sales_channel_key` 7.426; `fact_purchase_order_item` 1.630 nas duas). Os testes
`relationships` da declaração de `analytics` passam de 51 para 58 (a contagem 44 → 51 era a do `nl_sql`,
sobre as 25 tabelas; aqui entram também os da `fact_shipment`; a primeira contagem, 54 → 61, contava
outras ocorrências da palavra e foi corrigida na revisão, RVB1b-1-04). Contraprova: com `dim_brand` vazia numa
consulta somente leitura, o teste compilado acusa as 7.738 linhas.

### Bloco 3 — o texto (F5, F4, F8, G06)

- **F5:** a regra do pedido realizado no glossário (receita líquida, ticket médio, lucro bruto) e na
  descrição de `net_revenue_amount`. **Sai no passo 1 do Bloco 1b** (RVC-4-03); aqui só se confere
  que ele chegou à descrição curta do F4.
- **F4:** as três descrições erradas, e **todas** as que passam de 1.024 caracteres — o *manifest* de
  13/11 tem oito, quatro em `analytics` e quatro em `consumption`, não só as quatro que o `nl_sql`
  viu (RVC-1-04). Cada uma ganha uma versão curta e completa. A macro `bigquery__alter_column_comment`
  só roda no BigQuery, e o `make check` não a alcança: a guarda é **um teste local sobre o
  *manifest***, que mede o texto destinado ao BigQuery e recusa acima do limite, com contraprova. A
  macro pode recusar também, mas não é ela a prova. Onde a versão curta vive e como ela herda vão ao
  desenho junto com o do RVG-1-01. A aplicação real no BigQuery fica não medida.
- **F8:** "**Grão:**" nas 15 dimensões, e a descrição de tabela que falta em `dim_brand`,
  `dim_category` e `dim_payment_method` (F8+).
- **F11, F12, F13** (§2.2): a citação da P09 trocada pela regra; a coluna pela qual se agrupa cada
  dimensão conformada, ao lado da regra de identidade; a descrição de `fact_shipment_item.date_key`.
- **F14, F15, F16** (§2.2): as duas descrições de `fact_refund`; a regra no lugar da referência que o
  leitor do catálogo não alcança; "data de referência dos dados" no lugar de "do armazém".
- **G06:** o Bloco B do `PLANO_revisao_governanca.md`, na ordem que o RVG-1-02 corrigiu, com o
  desenho do RVG-1-01 revisado antes e os *snapshots* pelo RVG-1-03. A catraca baixa no mesmo
  *commit* de cada melhora.
- **Antes do F4 e do G06, a volta ao lote 3 da V1** (RVC-1-06): os dois mexem em
  `src/mvp_ed1/models/` (o contrato de descrição da ponte, `descriptions.py:295–303`). Cada item
  aplicável — 6 a 9 — sai com um resultado escrito: exercitado, limite preservado ou continua aberto.
  Não promete fechar a V1 inteira.

**Entregue em 14/11/2026.** F8 e F11 a F16 (`b326c66`); F4, a versão curta no BigQuery por
marcador no glossário e as três descrições erradas (`4e163c9`); G06, 102 das 141 colunas (`ff3bdfe`) e as 39 da
ponte pelo RVG-1-01 (`61e0543`, desenho revisado antes, sem ADR: o revisor não achou mudança de
ferramenta, camada, modelagem nem tratamento, e a N41 fica; **a confirmar pelo Owner**), com a catraca
baixada a zero em todas as camadas. **A revisão integral dos textos do Bloco 3 é do Owner** (CLAUDE.md §5). Os itens 6 a 9 da V1, que o RVC-1-06 manda revisitar antes do F4 e da
G06: o **6** (o escritor só edita `.yml` em bloco) ficou como limite preservado, porque os dois `.yml` à mão
novos e as promoções são em bloco; o **9** (macro nova e `dbt_project.yml` fora da conferência de *manifest*
atrasado) ficou como limite preservado, porque todo `make catalog` desta parte veio depois de um `make
dbt-build` completo; o **7** (formas de literal de instante) e o **8** (fonte de pacote) não se aplicam a
estes textos e continuam abertos.

**O desenho do RVG-1-01, para as 39 colunas que sobram da G06 (B1 e B3).** São colunas que a ponte do
legado calcula e que não têm par no `stg_retail__*`: as 36 `ingested_at` (no legado, o instante da
captura, `snapshot_at`, e não o carimbo do Airbyte), e, em `legado__inventory_movements`,
`event_sequence` (o desempate técnico da D40), `arrived_by_stream` (sempre falso) e `arrived_by_batch`
(sempre verdadeiro). Hoje o contrato (`descriptions.py`, o ramo `BRIDGES_FILE`) recusa texto na ponte
sem `description_from`, pela N41: a ponte só significa o que o par significa, por declaração. A proposta
mantém a regra e acrescenta uma segunda forma de declaração:

1. `legacy/ponte.py` ganha a tabela `TEXTOS_DA_PONTE` (`{apelido: texto}`), só para as colunas de
   `FORA_DA_ORIGEM` e a `event_sequence`, que é o que a ponte calcula e não copia.
2. O gerador escreve esses textos no `_pontes__models.yml` com `description_reason` fixo ("a ponte
   calcula a coluna; o texto é o de `TEXTOS_DA_PONTE`").
3. O contrato aceita texto sem `description_from` na ponte **só** se ele vier com esse motivo e for
   igual ao da tabela para aquele apelido. Qualquer outro continua recusado.
4. Contraprovas: texto na ponte sem motivo (recusa); com motivo e texto diferente do da tabela (recusa);
   apelido fora da tabela com motivo (recusa); a tabela com um apelido que tem par (recusa no gerador).
5. A catraca de `trusted` baixa de 39 para 0 no mesmo *commit*.

Não muda modelo, camada nem dado; é forma de declaração de texto. Se a revisão achar que ela contraria a
N41, volta ao Owner antes de implementar.

### Bloco 4 — o pacote do portal (D91)

A implementação da D91, **no formato fixado pelo Bloco 0b** ([Pacote de Metadados](docs/pacote_de_metadados.md)), com o contrato da guarda do RVG-1-04 e as contraprovas que ele pede (clone
sem artefatos, regeneração repetida, *commit* posterior sem mudança dos insumos), e antes dela a volta
ao item 9 da V1 — a conferência de *manifest* atrasado, de que a guarda depende (RVC-1-06). Entra **depois**
dos Blocos 1 a 3 para que a primeira versão do pacote já leve o texto corrigido, mas **antes** dos
Blocos 5 e 6, para que o `gdados` possa abrir a E1 sem esperar os ADRs. O formato acompanha versão
(como o `lineage --json`); o que os Blocos 5 e 6 acrescentarem entra como campo novo, sem quebrar.

Três coisas entram no contrato, vindas da emenda e da rodada 4 de revisão:

- **A fonte da página de estrutura e ambientes** (L4). O contrato diz, artefato por artefato, o que
  entra no pacote e o que o `gdados` lê direto por *commit* fixado: `docker-compose`, Terraform, mapa
  de paridade, Arquitetura, modelo de dados. A regra é a da D91: compor o que já é declarado, sem
  reimplementar. A evidência do GCP é **datada e congelada**, porque a infraestrutura foi destruída, e
  o pacote a rotula assim. As evidências coletadas no GCP, fora do Git no `mvp_eng_dados_1` (L10),
  entram ou não aqui, e sanitizadas como, nesta decisão de desenho.
- **A procedência do armazém** (L5). Primeiro o diagnóstico: se o banco já guarda alguma coisa da execução que
  o construiu, como o `invocation_id` do dbt ou um *commit* (não conferido). Depois a proposta, que liga o pacote e
  a leitura do BI ao mesmo *build*. Se ela pedir tabela ou *schema* novo, volta ao Owner antes de
  implementar. Até lá, a procedência do banco fica marcada **não verificada**, como o BI já faz.
- **O resultado dos testes** (RVC-4-01). O catálogo do BI mostra três estados por teste: declarado,
  executado com sucesso numa data, e problema em aberto hoje. A D91 leva só a procedência do
  `run_results.json`, que é ignorado pelo Git. O contrato leva, por teste, o objeto que ele guarda, o
  estado e a data, ligados à execução (`invocation_id`). Só campos sanitizados: nada da mensagem de
  falha nem do SQL compilado. Execução que não seja a do *manifest* do pacote é rotulada assim. Teste
  sem resultado aparece **sem resultado**: nunca se infere sucesso da declaração. As pendências
  documentadas (D62 a D64) ficam separadas.

**Entregue em 14/11/2026** (a primeira versão do pacote):

- o gerador `src/mvp_ed1/models/pacote.py`, chamado no fim do `make catalog`, no formato 1 já revisado;
  recusa escrever sem `manifest.json` e `run_results.json`, e recusa o pacote fora do esquema;
- a guarda no `check-offline` (`tests/test_pacote_gerado.py`): o `inputs_sha256` recalculado dos 314
  arquivos rastreados que alimentam o pacote, sem `dbt/target`; as contraprovas do RVG-1-04 (insumo
  alterado muda o digest; *commit* sem mudança de insumo não muda; clone limpo; regeneração repetida com
  os mesmos bytes);
- o `make test` grava o relatório JUnit em `data/pytest/junit.xml`, de onde sai o `checks`;
- **volta ao item 9 da V1** (macro nova e `dbt_project.yml` fora da conferência de *manifest* atrasado):
  pôr os dois entre os insumos do digest **não bastava** — regerar sobre o *manifest* atrasado dava o
  digest novo ao conteúdo antigo (RVB4-1-02). A guarda é o carimbo do *build*, que liga o *manifest* aos
  insumos do dbt lidos antes dele, e que o gerador confere;
- **L5, a procedência do armazém:** o banco não guarda nada da execução que o construiu (conferido no
  `information_schema`). A proposta é gravar `invocation_id` e *commit* numa tabela de `governance` ao
  fim de cada *build*; é tabela nova, e por isso **volta ao Owner** antes de implementar. Até lá, o
  pacote diz `not_verified`;
- **L10, as evidências do GCP** fora do Git no `mvp_eng_dados_1`: ficam `not_available`; se entram, e
  sanitizadas como, **é pergunta ao Owner**;
- tamanho: 4,3 MB, versionado como a D91 decidiu.

### L5 e Q6 — depois do Bloco 4 (decisões de 15/11/2026, §6 rodada 5)

**L5, a procedência do armazém — desenho, para revisão antes de implementar.** A [ADR-0023](docs/adr/0023-escopo-do-schema-governance.md)
já declarou em `governance` o conjunto *log de execução* ("cada execução de pipeline: início, fim,
resultado, versão do código"); esta entrega o materializa para o dbt, como a ADR-0044 materializou
`legacy_captures`, e a ADR nova registra a materialização.

**Revisto depois da rodada 1 da revisão do desenho** (`codex1_l5_desenho_r1.md`, RVL5-1-01 a 06). A garantia
é **estreita e conservadora**: o log registra toda execução do dbt que escreve o armazém, e só uma delas —
o `build` completo, limpo, de *commit* conhecido, sem nada depois — sustenta "este armazém foi construído
por este *commit*". Qualquer outra coisa deixa a procedência **não verificada**, e diz por quê. **O que "construído por este
*commit*" quer dizer** (RVL5-6-02): o código e a invocação da **última execução integral elegível**, sob as
materializações declaradas — não que essa invocação recriou cada linha. O `make dbt-build` não é
`--full-refresh`: a fato incremental relê só a janela de atraso do ramo `retail`, e os *snapshots* guardam
versões históricas por desenho. A procedência não certifica a origem de cada linha retida.

**Revisto de novo depois da rodada 2** (`codex1_l5_desenho_r2.md`, RVL5-2-01 a 05): o "completo" passa a ser
medido, e não lido dos argumentos; cada fase confirma a própria escrita; a linha aberta só sai por ato
explícito do custodiante.

1. **A tabela** `governance.dbt_invocations`, pela migração `0003_dbt_invocations` de `governance.py`
   (nunca editar as anteriores), **escrita em duas fases**, como `legacy_captures` (ADR-0044):
   - no `on-run-start`, a linha `started`: `sequence` (`bigint generated always as identity`: a ordem de
     abertura, dada pelo banco, e sem *grant* de sequência para inserir, RVL5-2-05 — **medido** em 15/11/2026 no
     armazém, numa transação desfeita: um papel só com `insert` insere na identidade, e no `bigserial` recebe
     `permission denied for sequence`), `invocation_id`
     (único), `command`, `git_commit` e `git_tree_dirty` (do ambiente; nulos quando a execução não os
     informa, como na DAG), `dbt_version`, `target` e `started_at` com `clock_timestamp()` **do banco**;
   - no `on-run-end`, **por último**, depois do *hook* de acesso, o fecho da mesma linha: `finished_at`
     (`clock_timestamp()` do banco), as contagens por estado dos `results` (`success`, `pass`, `warn`,
     `error`, `fail`, `runtime error`, `skipped`, `partial success`), `status` — `success` só sem nenhum de
     `error`, `fail`, `runtime error`, `skipped` e `partial success`; `failed` senão (RVL5-1-03), e `warn`
     contado sem reprovar — e `full_build`: **verdadeiro só se os resultados cobrem todo nó executável
     do grafo** (modelos, *seeds*, *snapshots*, testes e testes de unidade habilitados). É uma medida, não
     uma leitura de argumento: o `dbt retry` herda os argumentos e o comando do `build` e roda só o que
     falhou, e é pela cobertura que ele não passa por completo (RVL5-2-01). O `--select` também não.
   - **Cada fase confirma a própria escrita** (`commit` explícito no SQL do *hook*): o perfil PostgreSQL
     não tem *autocommit*, e devolver o `insert` ao dbt não o persiste (RVL5-2-02). A falha da abertura
     pula os nós (`skip_nodes_if_on_run_start_fails`, o padrão). **Prova em todo `build`:** um teste de dados
     singular confere, de outra conexão e durante a execução, que a linha `started` desta invocação está
     visível e aberta.
   Comando que não escreve o armazém (`test`, `docs generate`, `compile`, `parse`) não registra nada.
   **Mutação do armazém fora do dbt** (RVL5-3-01, RVL5-4-01): toda escrita suportada nas camadas que o dbt
   constrói, feita sem o dbt, registra-se em duas fases por `governance.registrar_mutacao(command)`: a linha
   abre e confirma **antes** da escrita, e fecha depois. Interrompida no meio, fica aberta e bloqueia;
   concluída, é uma execução parcial mais nova que o *build* anterior, e tira dele o `verified`. O
   **inventário**, levantado no repositório inteiro em 15/11/2026:
   - **registradas**: o descarte dos *snapshots* (`dbt-build RESET=1`, `dbt-drop-snapshots`;
     `drop_snapshots`); a adulteração da fato de trabalho por `make test FATO=1` (`test_fato_incremental`,
     aberta antes da adulteração e fechada depois do reparo; `test_fato`); a restauração da memória do
     armazém (`recovery-restore`, o `pg_restore` do passo 4; `recovery_restore`); **toda sincronização do
     Airbyte** (`airbyte_sync`, RVL5-5-02): o destino `retail` usa `full_refresh_overwrite` com
     `drop_cascade`, e a sincronização derruba as views de `staging` que dependem da tabela — não é só dado
     de entrada. O registro fica no funil único dos disparos, `mvp_ed1.airbyte`, que o `Makefile` e a DAG
     usam: a linha abre e confirma **antes** do disparo e só fecha quando o *job* chega a estado terminal
     observado (`succeeded`, `failed`, `cancelled`); se quem espera morre, ela fica aberta, porque perder
     o chamador não prova que o *job* parou;
   - **o log não é memória** (RVL5-5-01): o `pg_dump` da memória do armazém exclui
     `governance.dbt_invocations` e `governance.warehouse_provenance` (`--exclude-table`), e a restauração
     nunca os substitui — a linha `recovery_restore`, aberta antes do `pg_restore`, sobrevive a ele, e a
     ordem da `sequence` continua a do armazém. A conferência de contagens do passo 5
     (`_conferir_contra_o_banco`) deixa o log de fora, pela mesma razão. Numa máquina nova, o log nasce
     vazio e o primeiro `build` completo depois da restauração é o que verifica. **Na restauração**
     (RVL5-6-01): o `pg_restore --clean` da memória não pode descartar o schema `governance` nem a
     identidade do log, que ficam no destino — as entradas desses objetos saem da lista de restauração
     (`--use-list`), também ao ler um arquivo antigo que ainda traga o log dentro; em destino novo, a
     migração cria o log **antes** de restaurar a memória. A prova é uma restauração que **conclui**,
     preserva a linha corrente e a `sequence`, e é interrompida antes do *rebuild*;
   - **fora, com o motivo**: os testes do legado que escrevem em `trusted`, `quarantine` e `staging`
     (`test_legado_remocao`, `test_oraculo_da_memoria`) escrevem em **bancos efêmeros**; o DDL, os papéis
     e os *grants* de `governance garantir` não mudam o conteúdo das camadas construídas; o `psql`
     interativo é edição manual, que a regra inviolável 3 proíbe;
   - **o limite da garantia**: as camadas de **entrada** (`raw` pelo Airbyte e pelo *streaming*, `raw_legacy`,
     a captura do legado) mudam sem o dbt, e a garantia é sobre o **código** que construiu as camadas, não
     sobre o dado de entrada estar parado; uma view de consumo, `skus_below_reorder_point`, lê o *stream*
     ao vivo. O ADR o declara.
   **Guarda do próximo escritor:** um teste estático varre `src/`, `tests/`, `Makefile`, `docker/` e
   `airflow/` atrás de escrita SQL (`insert`, `update`, `delete`, `truncate`, `drop`, `alter` e `create` —
   inclusive `create or replace view` e `create table … as`, RVL5-5-03) nas camadas construídas, de
   `pg_restore` no armazém e de disparo do Airbyte fora do funil, e exige que cada arquivo esteja numa
   lista declarada, com o motivo (`registrar_mutacao` ou banco efêmero). **O alcance é lexical e
   declarado:** SQL montado dinamicamente não é visto, e uma escrita nova num arquivo **já** listado
   depende da revisão da mudança, não da guarda.
   **Os insumos estáveis** (RVL5-3-02): a coluna `inputs_confirmed` nasce falsa. O `CARIMBO_DEPOIS`, depois
   do dbt, refaz o *commit*, a sujeira e o digest dos insumos do dbt e, **só se os três são os de antes**,
   a marca verdadeira; se o passo não roda, ou se algo mudou, ela fica falsa e a execução não é verificada.
   O limite que sobra, declarado no ADR como precondição operacional: um arquivo editado e desfeito
   **dentro** do *build* não é visto — o *checkout* fica parado enquanto o dbt roda.
2. **O que fica sem fecho é visível** (RVL5-1-02): falha do *hook* de acesso (o dbt pula os *hooks*
   seguintes, e o fecho é o último), do próprio registro, ou interrupção deixam a linha `started` sem
   `finished_at`. **E ela bloqueia** (RVL5-2-03): enquanto houver linha aberta, nada é verificado — uma
   execução antiga ainda pode estar escrevendo, e a `sequence` ordena aberturas, não certifica que um
   executor morreu. A linha sai do caminho só por um ato explícito do custodiante, `make governance-abandonar
   INVOCACAO=…`, que a marca `abandoned` com o instante e nunca a dá por sucesso. É regra operacional
   nova, e vai ao ADR para o Owner.
3. **A regra de leitura** — uma só, numa *view* do próprio schema, `governance.warehouse_provenance`, que o BI
   e o pacote leem (RVL5-1-01): a candidata é a linha de maior `sequence`. É **verificada** se é
   `full_build`, `success`, de `git_commit` conhecido, `git_tree_dirty = false` e `inputs_confirmed`, se não
   há linha aberta, e
   se toda linha anterior terminou (ou foi abandonada) **antes** de ela começar — os dois instantes do
   relógio do banco. Senão, `not_verified`, com o motivo (execução parcial, sem fecho, *commit*
   desconhecido, árvore suja, reprovada, sobreposta). A DAG, que roda por camada, nunca sustenta procedência
   sozinha: o custodiante, antes de abrir a janela de leitura, roda `make dbt-build` de um *commit* limpo.
4. **O produtor dos metadados Git** (RVL5-2-04): o `CARIMBO_ANTES` do `Makefile` exporta, antes do dbt,
   `MVP_GIT_COMMIT` (`git rev-parse HEAD`) e `MVP_GIT_TREE_DIRTY`: `true` se há mudança em arquivo
   rastreado **ou** arquivo não rastreado e não ignorado nos insumos do dbt (`dbt/`, o glossário) — o modelo
   novo ainda fora do Git entra no *build* e não pode passar por limpo; os artefatos ignorados (`dbt/target`)
   não sujam. O `tree_dirty_at_generation` do pacote não muda de significado.
5. **Os papéis** (RVL5-1-04, RVL5-2-05): tabela e *view* declaradas como fontes de `governance` no gerador do
   legado, cada uma com `meta.grants`: na tabela, `select` para `auditor` e `transformer`, `insert` e
   `update` para `transformer`; na *view*, `select` para `auditor` e `transformer`. O `analyst` fica no
   contrato de consumo. O dbt e o leitor do pacote conectam hoje como o superusuário; os *grants* são a
   política, e `tests/test_acesso.py` a cobra por papel (`insert` com o padrão da identidade, `update`,
   `select` da *view*), com retenção (`permanent`), descrição e classificação.
6. **O pacote.** `provenance.warehouse` passa a ser o que a *view* diz **no momento da geração**, e só
   `verified` se a linha verificada é a da execução do *manifest* (`invocation_id` igual): é então que "o
   armazém é o do *manifest*", como a decisão da rodada 5 diz. Campos novos `built_from_commit`,
   `built_at`, `reason`; o formato continua o 1 (regra 3), e o esquema troca o `const not_verified` por
   `verified | not_verified`. A leitura usa a conexão do `.env`: o `catalog` e a 5ª etapa do `check`
   passam a carregá-lo (RVL5-1-05); sem conexão, `not_verified` com motivo "sem conexão", e nunca texto de
   erro do banco no pacote. O `check-offline` não chama o leitor. É a única leitura do banco que o pacote
   faz, e o contrato a declara. A comparação do `--check` tira o `warehouse` **inteiro** — desvio da
   primeira redação, que comparava `status` e `reason`, achado na implementação: o pacote é gerado antes do
   próprio *commit*, com a árvore suja, e um `make check` num *checkout* limpo o veria `verified`; a
   procedência é do ambiente, como o instante da execução.
7. **Os testes:** a migração do zero e sobre o armazém existente; a regra de leitura com linhas montadas
   (cada motivo, a linha aberta, a abandonada, a sobreposição, a ordem por `sequence`); a macro em
   integração — um `make dbt-build` completo (verificado), um `--select` e um `dbt retry` depois de uma falha
   (parciais), um `dbt test` (sem linha), o *hook* de acesso falhando antes do fecho (linha aberta, por uma
   variável só de teste), o descarte dos *snapshots* concluído sem o dbt chegar à abertura (não verificado) e
   o `RESET=1` bem-sucedido (verificado), um insumo alterado entre a coleta e o fim (`inputs_confirmed`
   falso), o teste da fato interrompido depois da adulteração e antes do dbt (não verificado), a
   sincronização que derrubou dependentes sem o dbt abrir depois (não verificado), a restauração de um
   pacote com o log dentro sobre um armazém com *build* posterior, interrompida antes do *rebuild* (não
   verificado, e o log não substituído) —; a guarda estática com um escritor novo fora da lista, inclusive
   um `create or replace view` (falha); o mapa de estados com um `build` que reprova teste e pula dependentes; a sujeira
   com modelo novo não rastreado, mudança rastreada e metadados ausentes; os papéis; o gerador com leitor
   substituto e sem conexão; o esquema aceitando `verified` só com os campos. Aviso em Consumidores §5. O
   ADR novo (o próximo número) registra a garantia estreita e a regra do abandono.

**Q6, as colunas em português** de `trusted.legacy_order_totals_divergence`. A decisão enumerou três; a
revisão do desenho achou a quarta (RVL5-1-06), e o Owner a incluiu em 15/11/2026. Passam a
`accepted_item_count` (`itens_empilhados`: o `.yml` a descreve como os itens aceitos), `rejected_item_count`
(`itens_rejeitados`), `rejection_reasons` (`motivos_da_rejeicao`) e `explained_by_quarantine`
(`explicada_pela_quarentena`, com o teste `not_null` que a acompanha). Só o modelo e o `.yml` dele as leem
(conferido), nenhuma view; os derivados — o pacote (`relations`, `lineage`, o identificador do teste),
o dicionário e a linhagem — saem da regeneração. A linha `prevista` em Consumidores §5 sai num *commit*
antes do que renomeia, e vira `feita` com o *build*.

**Implementado em 15/11/2026** (a Q6 em `5fcda58`, `4f10bca`; a L5 em `b56b2bc`, `db6d78c` e `1182240`, com as
respostas à revisão em `8818005`, `4152272`, `8db57e3` e no *commit* que a fecha; rodadas 29 a 32 do §9):
exercitado no armazém de trabalho um `make dbt-build` integral (`full_build` medido, aprovado, insumos
confirmados; `dirty_tree` enquanto a mudança não estava versionada), um `--select` (`partial_execution`) e um
`dbt test` (sem linha). Num armazém efêmero, a regra de leitura inteira, o registro da sincronização do
Airbyte e a restauração da memória com um arquivo que traz o log (concluída, log e ordem preservados; com o
filtro da lista desligado, o log é substituído). **Não exercitados:** o teste da fato envolto no registro
(exige `make test FATO=1`, que o Owner autoriza); o `dbt retry` depois de uma falha e o *hook* de acesso
falhando antes do fecho, num `build` de verdade (a cobertura e a ordem dos *hooks* estão provadas por
construção e pelo log); a restauração no armazém de trabalho (`RESTAURAR=1`).

**Medido depois da revisão:** o primeiro `verified` — o *build* do `make check` em `1182240`, com a árvore limpa
(invocação `7416daae-e3e3-48b6-b236-3ac3da0d92f6`), na *view* e no leitor do pacote com o *manifest* da mesma
invocação; e um `make dbt-build DBT_ARGS='--exclude-resource-type unit_test'` (941 nós, os 948 menos os 7 testes de
unidade) que sai `partial_execution` (RVL5I-1-01). A sincronização real do Airbyte e a DAG com o log continuam
não exercitadas; o que falta no BigQuery está nas Pendências, V3, item 10.

### Bloco 5 — domínios e métricas (F7, F9)

Pela Q3-a. O ADR do formato preserva as chaves de `meta` que já existem (`sensitivity`,
`description_from`, `description_inherited`, `description_reason`); o significado nasce no `.yml`
declarativo, nunca no `_derived.yml`. Em qualquer formato, cada valor e cada métrica é conferido contra o dado ou
contra a view por teste — a verificação do `nl_sql` (23 de 23 gabaritos reproduzidos só a partir
das definições) é o modelo. A referência é a view de `consumption` **auditada no Bloco 1b**, cujo
resultado já foi conferido contra o cálculo independente; métrica sem view auditada não se dá por
conferida (Q9-a). O texto das regras do F9 já existe em prosa desde o passo 1 do Bloco 1b; aqui ele
ganha a forma estruturada e o ADR (RVC-4-03).

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

O fechamento declara o que **não** foi provado (L9): as descrições curtas e as *constraints* `NOT
ENFORCED` nunca foram aplicadas no BigQuery nesta fase. Para o `nl_sql`, o efeito sobre o Gemini
continua sendo medição dele, no GCP dele. Declara também, conforme a Q9, quantas das 16 views foram
auditadas, e quais.

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

### Rodada 2 — Q5 a Q7 depois do Bloco 4; a Q8 no Bloco 1, antes do SQL do F2

| | Pergunta |
|---|---|
| **Q5** | A primeira *tag* deste repositório: o nome (`v2.1.0`, `v3.0.0`) e o que ela fecha |
| **Q6** | A O1 do `PLANO_revisao_governanca.md`: renomear para inglês as três colunas de `trusted.legacy_order_totals_divergence`, ou registrar como exceção |
| **Q7** | O F3, se a causa medida for regra. **Respondida em 14/11/2026: manter a regra** (a D35: a dimensão conta o pedido realizado; a divergência fica declarada e testada), a recomendada, coerente com a D66 |
| **Q8** | **Respondida em 14/11/2026 pelas recomendações** (ADR-0052). O F2, sobre a proposta do passo 2: a média no tempo, a valorização do estoque médio, os cortes do trimestre e o fuso, o evento atrasado, o par cujo histórico não reconstrói o saldo (legado com movimento rejeitado) — e se a regra pede ADR. Perguntada **no Bloco 1**, logo depois do diagnóstico, e não com as outras (RVC-1-02) |

### Rodada 3 — Q9 a Q11, da emenda (§2.1): respondida em 13/11/2026

Elas mudam o escopo, por isso vieram antes de executar. **Decisão do Owner: Q9-a, Q10-a e Q11-a**, as
recomendadas. As opções, como foram apresentadas:

| | Pergunta | Recomendação | Alternativas |
|---|---|---|---|
| **Q9** | L6: as 14 views que ninguém examinou | **(a)** Um **Bloco 1b**, depois do F1 e do F2, que audita as 16 views pelos três critérios da 2.11 do BI. Cada view é comparada com um cálculo independente sobre `analytics`, escrito a partir do glossário e não do SQL da view. Defeito vira F novo pela regra de entrada (Bloco 0, item 3); view sem defeito ganha o resultado escrito "auditada em `<commit>`". **Por quê:** o BI publica as 16 e o portal exibe as 16; corrigir duas e calar sobre 14 repete o padrão que o `nl_sql` revelou, e a 2.11 do BI faria a mesma auditoria do lado de lá, sem poder corrigir. **Custo:** o maior bloco depois do G06, sem estimativa | (b) Auditar só as views da primeira publicação do BI (P01 e P13), além do F1 e do F2; as outras ficam "não auditadas" no pacote, e a 2.11 do BI devolve o que achar. (c) Não auditar aqui: o pacote e o fechamento dizem "2 de 16 corrigidas por achado externo, 14 não auditadas" |
| **Q10** | L7: a D66 nesta fase | **(a)** Trazer a D66 para esta fase, como pergunta própria com as alternativas dela, decidida **antes do Bloco 4**, sobre o que já foi medido (M27 do BI). Se a resposta for a fato no grão da remessa (ADR-0033), ela vira bloco próprio, com ADR, antes do Bloco 5. **Por quê:** a primeira publicação do BI leva a P13, e o pacote nasceria com a limitação | (b) Manter adiada: a limitação segue declarada na descrição da view, no relatório da P13 (N43 do BI) e no pacote. São 12 remessas legadas em 3.310 entregues; o BI já se protege. É a opção de menor custo, e a lacuna continua aberta |
| **Q11** | L8: um portal ou dois | **(a)** O contrato daqui é **um só**: o pacote da D91 serve a qualquer portal. Quantos portais existem é decisão das sessões do `gdados` e do BI, e o aviso do Bloco 0 leva a pergunta às duas. **Por quê:** este repositório não decide o escopo dos outros (§1.1), e um pacote só evita duas leituras da mesma governança que divergem | (b) Decidir aqui que o `gdados` é o portal e que a 2.7 do BI aponta para ele: o aviso leva a decisão, não a pergunta. É mais simples, mas decide no lugar das duas sessões. (c) Dois contratos: o BI continua lendo *manifest* e YAML por *commit* (§3.5 dele), e o `gdados` lê o pacote. Não dá trabalho aqui, e as duas leituras podem divergir |

### Rodada 4 — Q12 a Q14, do alinhamento central (§2.2): respondida em 14/11/2026

| | Pergunta | Decisão do Owner | Alternativas apresentadas |
|---|---|---|---|
| **Q12** | O `gdados` e a etapa 2.7 do BI são dois portais? Leem o mesmo pacote? (L8; A7/D05 do `gdados`; §7 do BI) | **Dois portais, um pacote**: cada um mantém o escopo do próprio plano e lê só o pacote daqui; a parte comum nasce do mesmo pacote e não diverge; os dois andam independentes. Era a recomendada | Dois com escopos divididos (o BI aponta para o `gdados`, e a vitrine pública passa a depender da D04 do `gdados`); um só, o `gdados`; um só, a 2.7 |
| **Q13** | Quando sai o formato do pacote (L12) | **A especificação já**, no Bloco 0b: documento, esquema e exemplo, revisados; o Bloco 4 gera depois. Era a recomendada | Manter a ordem (os consumidores esperam o Bloco 4); adiantar o Bloco 4 inteiro |
| **Q14** | Quando o `nl_sql` sobe o projeto GCP dele | **Nenhum recurso novo no GCP**, em nenhum projeto. O `nl_sql` constrói a estrutura dele e sobe em outras nuvens, não agora no GCP. Resposta do Owner fora das opções | Subir agora só com a C0; subir no passo 4 do `nl_sql` |

### Rodada 5 — depois do Bloco 4: respondida em 15/11/2026

| | Pergunta | Decisão do Owner | Alternativas apresentadas |
|---|---|---|---|
| **L5** | A procedência do armazém: o banco não guarda qual execução nem qual *commit* o construiu, e o pacote diz `not_verified` | **Tabela em `governance`**: ao fim de cada *build*, o `invocation_id` e o *commit*; o pacote passa a dizer `verified` quando o armazém é o do *manifest*. Objeto novo no armazém, por isso com ADR, e mudança do esquema do pacote (o `verified` entra no formato, com aviso em Consumidores §5). Era a recomendada | Manter `not_verified`; adiar como verificação (Vn) |
| **L10** | As evidências do GCP, fora do Git no `mvp_eng_dados_1` (arquivado), entram no pacote? | **Ficam `not_available`**; o Registro da fase GCP, versionado aqui, conta o processo. Era a recomendada | Trazer um recorte saneado para este repositório |
| **RVG-1-01** | O texto próprio das 39 colunas da ponte (`TEXTOS_DA_PONTE`, `61e0543`) pede ADR? | **Dispensa ADR**: forma de declarar texto, dentro da N41. Era a recomendada | Um ADR curto |
| **Q6** | A O1: as três colunas em português de `trusted.legacy_order_totals_divergence` (e a quarta, `explicada_pela_quarentena`, achada na revisão do desenho e incluída pelo Owner em 15/11/2026) | **Renomear para inglês**, em entrega própria, com o que as lê, e o aviso de mudança de esquema em Consumidores §5 (`prevista` antes, `feita` depois). Era a recomendada | Registrar como exceção |
| **Q5** | A primeira *tag* deste repositório | **`v2.1.0`, no fim da fase**, depois dos Blocos 5 e 6: continua a numeração do `v2.0.0`, porque nada quebra para quem lê. Era a recomendada | `v3.0.0` no fim da fase; `v2.1.0` já, em `7d9548f` |

**Os textos do Bloco 3: aprovados pelo Owner em 15/11/2026**, sem a revisão integral, que ele declarou não poder fazer; a aprovação se apoia nas três rodadas de revisão do Bloco 3 (§9, rodadas 18 a 20).

## 7. Definição de pronto aplicada

A do [`CLAUDE.md` §7](CLAUDE.md#7-definição-de-pronto), por bloco. O que muda nesta fase:

- cada número corrigido tem o caso de antes e de depois medido no armazém local, e um teste que o
  guarda;
- cada bloco atualiza a entrada correspondente dos Achados do nl_sql ("replicado aqui em `<commit>`")
  e a V2;
- o pacote da D91 regenerado e em dia em cada *commit* depois do Bloco 4.

## 8. Ordem

1. ~~Rodada 1 (§6). Revisão deste plano por outro agente~~ (rodadas 1 a 3, §9; fechada sem achado aberto).
2. ~~Rodada 3 de perguntas (Q9 a Q11)~~ (respondida) e revisão da emenda (§2.1) por outro agente (rodadas 4 e 5, §9; fechada sem achado aberto).
3. ~~Bloco 0, com o aviso ao `nl_sql` primeiro~~ (entregue em 13/11/2026); ~~o alinhamento central (§2.2), a rodada 4 de
   perguntas e o Bloco 0b~~ (entregues em 14/11/2026).
4. Blocos 1, 2 e 3, cada um revisado antes do seguinte. No Bloco 1, o F2 para depois do diagnóstico
   e da proposta, até a **Q8**; o F1 e o F3 seguem. Pela Q9-a, o Bloco 1b vem depois do F1 e do F2:
   a definição (com o F5 e o texto do F9), a referência e a contraprova. Pela Q10-a, a D66 é
   perguntada antes do Bloco 4 (§3, "D66"), e a auditoria da P13 só conclui depois dela.
5. Bloco 4.
6. Rodada 2 de perguntas (Q5 a Q7); Blocos 5 e 6, com os ADRs.
7. Fechamento.

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

### Rodada 3 — Codex conta 2, sobre `32f1097` (13/11/2026, 05:15)

`gpt-6.1-sol`, esforço *high*, só leitura, restrita ao RVC-1-02 e a regressões. Veredito: **nenhum
bloqueante no escopo revisado** — RVC-1-02 **resolvido**, os outros oito preservados, nenhum achado
novo. Relatório em `data/medicoes/base_consumidores/codex2_plano_r3.md`. A observação de que o título
da rodada 2 de perguntas parecia pôr a Q8 depois do Bloco 4 foi atendida no título, sem mudar a ordem.
**A revisão do plano está fechada.**

### Rodada 4 — Codex conta 2, sobre a emenda em `976c44c` (13/11/2026, 19:41)

`gpt-6.1-sol`, só leitura, com o dossiê `REVISAO.md` (`make check` verde, 1360 *passed*). Veredito:
**mudanças necessárias** — um bloqueante e três ajustes. L1 a L9 conferem com os planos dos
consumidores, e os RVC-1-01 a 09 ficam preservados. Relatório, pedido e *log* em
`data/medicoes/base_consumidores/` (`codex2_plano_r4*`). Cada achado foi reproduzido antes da resposta.

| # | Onde | Achado | Veredito | Situação |
|---|---|---|---|---|
| RVC-4-01 | Bloco 4 / D91 / Q11-a | O contrato comum não leva o resultado datado dos testes por objeto, e o catálogo do BI distingue declarado de executado | ajuste | **Aceito.** Reproduzido: `bi-como-codigo/PLAN.md:340–342` (os três estados); a D91 cita só `generated_at` e `invocation_id`; `dbt/target/run_results.json` ignorado (`.gitignore:51`). O Bloco 4 ganhou o item "O resultado dos testes", com campos sanitizados e a ausência explícita |
| RVC-4-02 | Bloco 1b; D66; §8 | A referência só sobre `analytics` não vê os deltas e as reservas da P12 e conserva a população que a fato da P13 perdeu | bloqueante | **Aceito.** Reproduzido: `perguntas_de_negocio.md:192–209` (P12 = fato + deltas não absorvidos); `skus_below_reorder_point.sql:66,157` (`inventory_movements_stream`, `inventory_balances`); `fact_shipment_item.sql:51–54` parte de `shipment_items`. O passo 2 do 1b declara as fontes por pergunta, com corte consistente e população contra a camada responsável; a P13 só conclui depois da D66, e é refeita se vier fato nova |
| RVC-4-03 | Blocos 1b, 3 e 5; §8 | A auditoria precisa de definições que o F5 e o F9 só completam depois dela | ajuste | **Aceito.** Reproduzido: `receita_liquida.md:5–12` sem o pedido realizado; a P09 (`perguntas_de_negocio.md:158–165`) sem a população, que só está em `payment_approval_rate_by_method.sql:3–5,35–36`. O passo 1 do 1b antecipa o F5 e o texto do F9 em prosa; o Bloco 5 mantém a forma estruturada e o ADR; o §8 diz a ordem |
| RVC-4-04 | Bloco 1b, contraprova | Comparar o F1 e o F2 já corrigidos não prova que a referência detecta o defeito | ajuste | **Aceito.** O passo 3 do 1b roda o SQL defeituoso, do *commit* anterior à correção, como consulta somente leitura: a referência acusa a diferença e passa com a view corrigida, sem escrever no armazém |

### Rodada 5 — Codex conta 2, sobre `e3252a5` (13/11/2026)

`gpt-6.1-sol`, só leitura, restrita às respostas da rodada 4 e a regressões. Veredito: **nenhum
bloqueante no escopo revisado**. RVC-4-01 a 04 estão **resolvidos**, não há achado novo, e os achados
das rodadas 1 a 4 ficam preservados. Relatório em `data/medicoes/base_consumidores/codex2_plano_r5.md`.
**A revisão da emenda está fechada.**

### Rodada 6 — Codex conta 2, sobre o Bloco 0b em `0b99607` (14/11/2026)

Relatório em `data/medicoes/base_consumidores/codex2_bloco0b_r1.md` (fora do Git). Dois bloqueantes e
dois ajustes, todos reproduzidos e aceitos.

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVB-1-01 | A procedência do formato não comportava a árvore limpa ou suja nem o ambiente que a D91 pede | bloqueante | Feito: `provenance.tree_dirty_at_generation` e `provenance.environment.dbt_target`, com o significado escrito sem autorreferência (o que prova é o `inputs_sha256` no *commit* fixado); duas contraprovas |
| RVB-1-02 | O esquema aceitava estado sem evidência: `pass` sem data, `audited` sem *commit*, critérios e referência, armazém `verified`, `run_results` sem procedência | bloqueante | Feito: condições `if/then` no esquema; armazém só `not_verified` na versão 1; procedência do `run_results` obrigatória; cinco contraprovas, um caso legítimo de auditoria que passa e a conferência do `invocation_id` entre seções, no teste e como dever do gerador |
| RVB-1-03 | "Mesma regra da catraca" não definia o universo das faltas, e a catraca percorre o materializado | ajuste | Feito: `description_gaps` é o universo **declarado**; a especificação diz que o pacote não vê coluna materializada sem declaração, e que essa garantia é da catraca no `check` |
| RVB-1-04 | O registro de mudança de esquema pedia a linha depois da publicação e antes do *commit* | ajuste | Feito: coluna Estado (`prevista`, `feita`) e a sequência escrita em Consumidores §5 |

**Rodada 7** (codex2, sobre `50d58b1`, relatório `codex2_bloco0b_r2.md`): RVB-1-01, 03 e 04 resolvidos;
RVB-1-02 **parcial**, porque a string vazia ainda passava por referência e por `invocation_id`.
Respondido: `minLength` nos identificadores, na referência e em todo texto opcional (a ausência é
`null`, nunca `""`); quatro contraprovas novas; a conferência entre seções exige identificador
preenchido.

**Rodada 8** (codex2, sobre `9b1f246`, relatório `codex2_bloco0b_r3.md`): RVB-1-02 resolvido, nenhum
achado novo. **A revisão do Bloco 0b está fechada.**

### Rodada 9 — Codex conta 2, sobre o Bloco 1 em `c1db9ae` (14/11/2026)

Relatório em `data/medicoes/base_consumidores/codex2_bloco1_r1.md`; dossiê em `REVISAO.md`. O revisor
não alcançou o Docker e julgou o SQL e as *fixtures* estaticamente.

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVL1-1-01 | Dia com posição e sem entrada acumulada ficava sem valor e saía da média: média parcial publicada como do trimestre | bloqueante | Feito em `9d50cca`: valor médio e giro indefinidos com um dia assim; par E no teste de unidade, com contraprova |
| RVL1-1-02 | A reconciliação da P15 não via denominador nulo (`min`/`max` ignoram nulo) | ajuste | Feito: contagem das linhas com e sem denominador; contraprova acusa 1 linha |
| RVL1-1-03 | `<>` deixava passar a contagem nula da dimensão | ajuste | Feito: `is distinct from`; contraprova acusa 1 cliente |
| RVL1-1-04 | A *fixture* do F2 não protegia o corte no primeiro movimento | ajuste | Feito: par C; contraprova 8,67→6,50 |
| RVL1-1-05 | A causa dos 1.216 indefinidos estava atribuída sem medição | ajuste | Medido: 1.212 com correção-relâmpago no trimestre; saídas literais em `bloco1/rvl1_saidas.md` |

### Rodada 10 — Codex conta 2, sobre `9d50cca` (14/11/2026)

Relatório em `codex2_bloco1_r2.md`. RVL1-1-01 a 04 resolvidos; RVL1-1-05 parcial (os números sem
saída literal); um achado novo:

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVL1-2-01 | O `9d50cca` reescreveu o ADR-0052 aceito (AGENTS.md, regra 3) | ajuste | Feito: o ADR volta ao texto aceito; a regra do dia sem custo foi para o glossário e para a descrição da view, e as medições para a V4 e este plano, com as saídas literais |

### Rodada 11 — Codex conta 2, sobre `1159059` (14/11/2026)

Relatório em `codex2_bloco1_r3.md`. RVL1-2-01 e RVL1-1-05 resolvidos; três ajustes de texto, todos
feitos: a nota do F1 nos Achados diz os dois grãos (RVL1-3-01); a do F2 diz que o giro fica indefinido
pela posição zero em todo o trimestre, e não pela correção-relâmpago em si, que aparece também em 114
trimestres de valor positivo (RVL1-3-02); a pendência das notas de replicação aponta para os *commits*
feitos (RVL1-3-03). **A revisão do Bloco 1 está fechada.**

### Rodada 12 — Codex conta 2, sobre o bloco da D66 em `f4ab54a` (14/11/2026)

Relatório em `data/medicoes/base_consumidores/codex2_d66_r1.md`. Dois bloqueantes, um ajuste e uma
observação:

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVD-1-01 | O teste de população da P13 passava pela `dim_date`, e uma entrega sem data conformada sumiria dos dois lados | bloqueante | Feito: o mês sai do instante, e a remessa entregue sem `delivered_date_key` é acusada à parte; contraprova acusa 1 mês |
| RVD-1-02 | O texto copiado da fato de item prometia, em `is_cycle_closing_shipment` e `order_delivered_at`, o fechamento do ciclo que o SQL só garante com `is_order_cycle_closed`; o `description_reason` de `failed_attempt_count` falava de item | bloqueante | Feito nas duas fatos de remessa (a de item tinha o mesmo defeito) |
| RVD-1-03 | O comentário prometia uma reconciliação entre as duas fatos que não existe | ajuste | Feito: o comentário diz o que cada uma reconcilia, e o limite foi para o Modelo de Dados §3; o ADR-0053 fica como foi aceito |
| RVD-1-04 | A D66 consta como `feita` em Consumidores §5 antes do *push* | observação | Sem mudança: a linha só se lê no GitHub junto com os *commits* que ela cita |

### Rodada 13 — Codex conta 2, sobre `2b881d0` (14/11/2026)

Relatório em `codex2_d66_r2.md`. RVD-1-01, 03 e 04 resolvidos; RVD-1-02 parcial; dois ajustes de texto,
feitos: `failed_attempt_count` herda o texto de `shipments`, que já dizia a aditividade (RVD-2-01); os
cabeçalhos das duas fatos de remessa dizem que a P14 lê `fact_shipment` desde o F17 (RVD-2-02).

### Rodada 14 — Codex conta 2, sobre `697fcd7` (14/11/2026)

Relatório em `codex2_d66_r3.md`. RVD-1-02, RVD-2-01 e RVD-2-02 resolvidos, nenhum achado novo. **A
revisão do bloco da D66 está fechada.** O *push* espera o fechamento da revisão do 1b, porque os
*commits* dos dois blocos se intercalam no `main`.

### Rodada 15 — Codex conta 2, sobre o Bloco 1b e o Bloco 2 (14/11/2026)

Relatório em `data/medicoes/base_consumidores/codex2_bloco1b_r1.md`. Um bloqueante, três ajustes e uma
observação, todos aceitos:

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVB1b-1-01 | A população dos denominadores de pedidos da P02 e da P15 não era conferida | bloqueante | Feito: a P15 passa ao grão do pedido (`0471f6a`, F21) e ganha conferência contra `trusted.orders`; a P02 mantém o recorte, declarado (a receita do pedido de itens rejeitados não é conhecida), como o `order_count` das outras views de receita |
| RVB1b-1-02 | A contraprova do F1 aceitava diferença de agrupamento | ajuste | Feito: um teste reduz os denominadores e exige divergência |
| RVB1b-1-03 | As Perguntas de Negócio ainda citavam a fato de item na P04 e na P14 | ajuste | Feito, com a P15 |
| RVB1b-1-04 | O plano dizia 54 → 61 `relationships`; são 51 → 58 | ajuste | Feito |
| RVB1b-1-05 | Referências que reproduzem o cálculo; a da P03 conservava o grão do F20 | observação | Feito na P03 (chave natural, "VÁRIOS"); nas outras, limite declarado |

### Rodada 16 — Codex conta 2, sobre `0471f6a`, `504271a` e `ba67981` (14/11/2026)

Relatório em `codex2_bloco1b_r2.md`. RVB1b-1-02 e 04 resolvidos; 01, 03 e 05 parciais. Três achados, feitos:
a conferência do denominador da P15 deixou de descartar os nulos (RVB1b-2-01, bloqueante; contraprova
acusa 1 linha); os resumos de fonte da abertura comercial e do cabeçalho da P15 (RVB1b-2-02); o limite das
referências de construção parecida (P05, P07, P13, P14) no teste e aqui (RVB1b-2-03).

### Rodada 17 — Codex conta 2, sobre `4da9e60` (14/11/2026)

Relatório em `codex2_bloco1b_r3.md`. RVB1b-2-01 a 03 e os parciais RVB1b-1-01, 03 e 05 resolvidos, nenhum
achado novo. **A revisão do Bloco 1b e do Bloco 2 está fechada.** O *commit* do fim da auditoria das 16
views, que o `bi-como-codigo` fixa (N85 de lá), é o `4da9e60`; o anúncio em Consumidores §6 sai com o
*push*, que espera a revisão do `8742a59` (os campos novos do pacote) e do Bloco 3, intercalados no
`main`.


### Rodada 18 — Codex conta 2, sobre o Bloco 3 (14/11/2026)

Relatório em `codex2_bloco3_r1.md`. Três bloqueantes e um ajuste, todos aceitos:

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVB3-1-01 | A palavra "gerado" no cabeçalho de `_entregas__models.yml` e `_captura__models.yml` os fazia `generator`, fora da herança | bloqueante | Feito (`b2360d6`): gerado é só o `.yml` cuja 1ª linha começa com `GENERATED_MARK`; a sonda de propagação do revisor virou teste |
| RVB3-1-02 | `payments.net_captured_amount` prometia reconciliar com a receita | bloqueante | Feito (`b22fdcb`): saldo de capturas menos reembolsos aprovados, no universo do valor cobrado; não é receita de produto |
| RVB3-1-03 | O texto curto de recompra, ciclo e pontualidade deixava regras que mudam o número depois do marcador | bloqueante | Feito (`7ad2943`; residual na rodada 19) |
| RVB3-1-04 | A guarda do F4 exercitava uma cópia Python da macro | ajuste | Feito (`4d9cb73`): o teste renderiza a macro real com o Jinja do dbt e mata quatro mutantes |

### Rodada 19 — Codex conta 1, sobre `b2360d6`..`4d9cb73` (14/11/2026)

Relatório em `codex1_bloco3_r2.md`. RVB3-1-01, 02 e 04 resolvidos; 03 parcial. Um bloqueante, feito: o texto
curto da pontualidade passa a dizer que a chegada é o `delivered` **mais recente** (RVB3-2-01, `f5b34b5`).

### Rodada 20 — Codex conta 1, sobre `f5b34b5` (14/11/2026)

Relatório em `codex1_bloco3_r3.md`. RVB3-2-01 e RVB3-1-03 resolvidos, nenhum achado novo. **A revisão do
Bloco 3 está fechada.** Seguem com o Owner a revisão integral dos textos e a confirmação da dispensa de ADR
do RVG-1-01. O `0ecf270` (o `::` na revisão de segredos) e o `68b1535` (Bloco 4) vão à revisão juntos.

### Rodadas 21 a 28 — Codex conta 1, sobre o Bloco 4 (14/11/2026)

Relatórios em `codex1_bloco4_r1.md` a `r8.md`; objeto inicial `68b1535` (o gerador) e `0ecf270` (o `::` na
revisão de segredos). Antes de enviar, achado meu: o pacote de `68b1535` carregava um JUnit antigo com 1
falha (regenerado em `7ef9f20`). As rodadas, com o que cada uma deixou:

| Rodada | *Commit* respondido | Achados | O que mudou |
|---|---|---|---|
| 1 | `3d704c0` | 4 bloqueantes, 3 ajustes (RVB4-1-01 a 07) | Carimbo do *build*; 5ª etapa do `make check`; leitores que recusam; JUnit pelo arquivo real; caminho de máquina recusado; calendário; árvore suja inteira |
| 2 | `415d6b1` | 4 bloqueantes, 2 ajustes | Normalização por caminho (a 5ª etapa acusaria todo *build*); `dbt/**/*` no digest; completude do JUnit pela coleta; carimbo pela invocação |
| 3 | `9526117` | 2 bloqueantes | `checks: {}` nunca publicável (`--conferir-pytest` no `check-offline`) |
| 4 | `3fa601d` | 1 bloqueante, 1 ajuste | Leitor de blocos do Markdown (depois removido) |
| 5 | `b0bcdd0` | 4 bloqueantes | A cobertura passa a se conferir contra o **declarado** (P01–P16; o cabeçalho das Pendências com o Registro), e não relendo o Markdown |
| 6 | `81b1b9a` | 2 bloqueantes | Regra de autoria da seção 1; toda linha da tabela do Registro conta |
| 7 | `acb26d0` | 1 bloqueante, 1 observação | Tabela do Registro por bloco; alcance lexical declarado no contrato |
| 8 | — | nenhum | **A revisão do Bloco 4 está fechada.** |

Da rodada 7 em diante, o pedido ao revisor calibrou a gravidade: bloqueante só para caminho concreto de
perda ou invenção de item com documento escrito de boa-fé; forma exótica, observação com o limite no
contrato. A primeira versão do pacote, que os consumidores fixam, é a de `acb26d0` (Consumidores §6).
Seguem com o Owner a L5 (procedência do armazém, tabela nova em `governance`) e a L10 (evidências do GCP).

### Rodadas 29 a 32 — Codex conta 1, sobre a implementação da L5 e da Q6 (15/11/2026)

Relatórios em `codex1_l5_impl_r1.md` a `r4.md`; objeto inicial `523f661..1182240` (a Q6, as duas partes da L5 e a
linha `feita` de Consumidores §5). O desenho tinha passado por seis rodadas antes (seção "L5 e Q6"). Antes de
enviar, achado meu: o pacote de `b56b2bc` estava atrasado (os insumos só viam o rastreado), corrigido em
`db6d78c`.

| Rodada | *Commit* respondido | Achados | O que mudou |
|---|---|---|---|
| 29 | `8818005` | 2 bloqueantes, 3 ajustes, 1 observação (RVL5I-1-01 a 06) | A cobertura do *build* integral exige os testes de unidade; o POST do Airbyte só fecha `failed` com recusa provada; a sincronização garante o `governance`; o log sai das contagens dos dois lados; a linha de §5 diz que faltou a `prevista`; a paridade do BigQuery vai às Pendências (V3, item 10). Achado meu na resposta: o `make sync-airbyte` não carregava o `.env` desde `db6d78c` |
| 30 | `4152272` | 2 observações | As funções do dbt entram na cobertura; `make airbyte-ativos` só conclui com a listagem completa ou que alcança `DESDE=` |
| 31 | `8db57e3` | 2 observações | O alcance exige o segundo inteiro (o Airbyte dá o início em segundos); a recusa do `gcp-airbyte-ativos` com 100 *jobs* fica dita |
| 32 | este fecho | 1 observação | O segundo de folga sai do `DESDE`, sem aritmética na sentinela de página sem início legível |

**A revisão da implementação da L5 e da Q6 está fechada.** Da rodada 30 em diante, nenhuma achou bloqueio; a
observação da 32 é de diagnóstico, com o conserto de uma linha provado pela contraprova do próprio revisor, e
por isso foi respondida no *commit* de fecho, sem rodada 33. A calibração foi a do desenho: bloqueante só para
caminho concreto, com operação suportada, que quebre promessa da ADR-0054 ou do contrato do pacote.
