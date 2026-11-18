# Plano — a reabertura da base: o retorno dos consumidores e as pendências que pedem regeneração

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 17/11/2026. **Aprovado** em 17/11/2026: revisado em cinco rodadas, a quinta sem achado (§7), e as Q64 a Q72 respondidas pelo Owner (§5). Nada foi executado |
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
| 17 | **F35: a quarentena das entregas não guarda a origem.** `quarantine.rejected_shipment_deliveries` lê `trusted.shipments`, que empilha as duas origens, sem `source_system`, e o `shipment_id` se repete entre elas. Na `v2.1.0`, a remessa 45 do legado está lá e só se identifica cruzando com `trusted.shipments` | Este projeto, na validação do Bloco 3 (Owner, 18/11/2026: registrar e corrigir na melhor forma) | Sim, o esquema da relação | 3 e 5 |

**Fica fora**, com o motivo:
- **Trocar o código `GW-OK`:** mudaria o dado, e o significado já está declarado (`nl_sql`, item 9).
- **A D43 e a V1 a V3:** o Owner não as incluiu, e nenhuma muda o que os consumidores leem.

---

## 2. Os blocos, na ordem

### Bloco 0 — a abertura (só documentos)

1. Registrar o F31 a F34 nos [Achados](docs/achados_nl_sql.md), pela regra de entrada (Consumidores
   §4), cada um com a origem (o consumidor que o levantou) e este plano como destino.
2. Uma linha `prevista` em Consumidores §5 para cada mudança de **esquema**: os campos novos do pacote (itens 6 e
   16). A regra da seção (A sequência de uma linha) faz valor e texto entrarem uma vez só, já `feita`. Por isso o
   dado das 16 views (itens 1, 2 e 7), as descrições (item 3), a nota do custo (item 4), a especificação
   (item 5) e os textos (itens 12 a 15) entram no fim, com o *commit* e o *build*. O que está previsto mudar de
   valor fica apontado para este plano no texto da seção.
3. Abrir a D93 nas Pendências para o item 1. A decisão vira ADR se a forma da Q64 pedir.
4. O README passa a apontar para este plano no estado do projeto.

### Bloco 1 — a operação (código e testes, sem dado)

Vem antes do ciclo, porque o ciclo passa por cada um destes itens e os mede.

- **D64:** a forma que a Q66 escolher. Recomendada: a opção (a) das Pendências, com a geração em base64
  seguro para URL nos dois lugares do `Makefile`, um teste em `tests/test_makefile.py` e a chave da máquina
  trocada ao recriar o Airflow.
- **D63:** a forma que a Q65 escolher. Recomendada: a opção (a) das Pendências. O medidor espera, com prazo,
  um sinal do ramo de alerta, e a restauração reposiciona o grupo do Beam no início do *log*. O sinal tem de
  provar a drenagem (RVRB-1-04), e nem o contador de `alertas_emitidos` parado nem o *watermark* passando do
  maior horário de evento a provam:
  - **o sinal:** o fechamento da última janela (`FixedWindows`, `AfterWatermark`, `streaming/pipeline.py`) que
    contém o maior `occurred_at` até o corte, observado depois de o ramo de alertas processar e publicar essa
    janela;
  - **zero alertas é legítimo** quando o oráculo por janela também dá zero. Os painéis só de *snapshot* não
    emitem alerta (`pipeline.py:226–232`);
  - **prazo esgotado é falha**, registrada como tal, nunca encerramento limpo;
  - o teste distingue um contador que parou de um ramo concluído e cobre a **execução sem produtor**, que é a da
    publicação (Bloco 5) e a do passo 7 da restauração.

  **O sinal ainda não existe e é entrega deste bloco** (RVRB-2-02). Hoje nada sai do *pipeline* quando uma janela
  fecha sem cruzar o limiar: `AcumularSaldoEAlertar.process` retorna sem emitir, tanto no *snapshot* quanto na
  janela comum (`pipeline.py:226–242`). E o `yield` de `PublicarAlerta` não confirma a entrega, porque o
  `produce` é assíncrono e o `poll(0)` não espera (`transport.py:282–291`). O Bloco 1 entrega:
  - **uma confirmação por janela concluída**, emitida também quando ela não gera alerta, com o fim da janela e as
    chaves processadas;
  - **a entrega confirmada do alerta** (o `flush` do produtor, ou o *callback* de entrega) antes de a confirmação
    contar;
  - **a leitura pelo medidor, pela cobertura de todo o corte** (RVRB-3-01). O medidor calcula, a partir do livro
    durável até o corte, o conjunto esperado de pares (chave, janela) e a contagem de eventos de cada par. Ele
    espera até que as confirmações cubram **todos** os pares, inclusive os das janelas anteriores e os painéis
    tardios: a confirmação leva a contagem acumulada do par, e o par fecha quando ela iguala a esperada. Com
    alerta, a confirmação só conta depois da entrega bem-sucedida. Confirmar só a última janela não basta, e
    também não basta a última janela de cada chave;
  - **o recorte da execução** (RVRB-4-01). O ramo de alertas só recebe os movimentos que o *sink* inseriu nesta
    execução, os `novos` do `INSERT ... ON CONFLICT DO NOTHING ... RETURNING` (`sink.py:187–203`,
    `pipeline.py:174–180,296–314`). O que já estava no destino entra só na semente de saldo
    (`pipeline.py:199–221`), sem painel nem confirmação. Então a expectativa é o conjunto **inserido por esta
    execução**, inclusive os do *snapshot* e os tardios, identificado pela execução. O *sink* registra os
    inseridos, numa marca no destino ou no próprio registro de confirmação. Se for uma coluna nova em
    `raw.inventory_movements_stream`, é mudança de esquema e entra na revisão integral do declarativo. Uma linha
    de base por `event_sequence` lida no início só serve se a equivalência for mostrada. As
    confirmações levam a mesma marca. A prova de que a origem inteira chegou ao destino até o corte continua
    separada, no `stream-wait`;
  - **as contraprovas:**
    - a última janela confirmada e um par anterior retido: a espera continua e, no fim do prazo, falha;
    - o destino já preenchido: os eventos antigos não pedem painel novo, todos os novos pedem confirmação, e
      retransmitir os antigos não muda a expectativa;
  - **atraso além da tolerância** (1.200 s, `pipeline.py:314–332`): o Beam descarta a janela expirada, a
    contribuição confirmada falta, e a espera falha pelo prazo. O evento nunca é tirado da expectativa para dar
    verde.

  O meio da confirmação (contador do Beam, registro em arquivo ou mensagem) é escolhido no desenho, com medida.
  **Se pedir um destino durável novo, como um tópico, volta ao Owner** antes de ser implementado (`CLAUDE.md` §5).
- **V7:** o `make recovery-restore` passa a chamar o `make ledger-treatment` no passo que constrói a
  quarentena da captura, com teste de que a época aberta sai com o registro.
- **V6:** primeiro a medida, depois a correção. O que fica no ar no desligamento: *threads daemon* e o
  `stderr` do Prism. Teste de que o encerramento limpo sai com o código 0. Se a causa não aparecer, a V6
  volta ao Owner com a medida, sem correção às cegas.

### Bloco 2 — a regeneração declarada (F31 e V5)

1. **Medir o alcance do produtor** antes de fechar a forma (Q64). Só leitura, no código e no armazém.
   - Que tabelas da origem ele escreve: `inventory_movements`, `inventory_balances` e outras.
   - Que modelos e views leem cada uma.
   - **Se o ciclo tira do armazém os eventos do exercício.** A regeneração das fontes, sozinha, não os tira
     (RVRB-1-01): o destino quente `raw.inventory_movements_stream` continua com eles, e o *staging* o une ao
     lote; o `merge` da `fact_inventory_movement` na partição `retail` não apaga o que sumiu da origem
     (`fact_inventory_movement.sql:56–89`); e os saldos cujo `updated_at` volta no tempo não chegam sem
     *reset* do cursor do Airbyte. Quem os tira é a **sequência de descarte** do Bloco 5, a do 5R (diário B1,
     B2, C2 e D3). A rodada 1 confirmou a sequência pela evidência do 5R: a B2 removeu 18.125 linhas do destino
     quente. Falta a medida desta fase, que é a conferência de resíduo zero do Bloco 5.
2. **A D93**, com a forma escolhida e a contrapartida na fase GCP. Na forma (e), não há ADR de tratamento de
   dados: muda a ordem do ciclo e entra uma guarda. As formas (a) e (b) pedem ADR (0057), porque mudam o
   contrato do evento (Modelo de Dados §5) ou a restauração.
3. **V5:** a declaração em `generator/geracao.yml` (abertura e compras pela demanda) e a meta da Q67, medida
   em memória no varejo antes do ciclo, como a V4 fez (Q42).
4. Guardas novas, uma por correção:
   - **para o F31, duas regras** (RVRB-1-03):
     - nenhum movimento com `occurred_at` depois da `as_of_date`, no fuso do gerador. Os *timestamps* de
       registro e de ingestão não entram;
     - toda saída por venda tem a remessa dela. O vínculo é o que o gerador grava (`generator/domains/estoque.py:153–163`):
       `source_type='sale'` e `source_id` igual ao `shipment_code` de uma remessa da mesma `source_system` na
       `fact_shipment`. Não há FK de movimento para remessa (`models/inventory.py:184–206`). Transferência,
       devolução e ajuste ficam fora da exigência.

       **O legado tem um caso que nenhuma junção explica** (RVRB-2-01). A injeção trocou o código da remessa 47
       por `N/A` (`NULL_DISGUISED`). O tratamento o anulou e rejeitou a remessa (`NULL_REQUIRED`). O movimento
       nasce antes da injeção e guarda o código anterior. A quarentena só tem o que o legado entregou
       (`legacy/dbt.py:189–249`, `classification.sql:185–206`), e o código original só existe no manifesto de
       injeção. Esse manifesto é oráculo de teste, não dado, e não pode alimentar a guarda. A forma da regra no
       legado é a **Q72**. Recomendada, a (d) (RVRB-3-02): a regra é estrita no varejo, onde o produtor escreve. No
       legado, a ausência explicada pela quarentena corrente com o código intacto passa. Os casos não
       demonstráveis são inventariados a partir do dado observado, e você aprova uma **lista explícita de
       exceções desta geração**, declarada e revisada por inteiro. A guarda **falha** para qualquer caso fora da
       lista. A lista é uma declaração versionada (um *seed* em `dbt/seeds/`, como `order_status_transitions`),
       lida só pela guarda. O diário guarda a evidência, mas não substitui a declaração, e nada é inserido à mão
       no banco. Cada exceção tem a identidade do movimento, o `source_id`, a captura, o catálogo e a impressão do
       tratamento, e a evidência fica congelada no diário. A lista é refeita a cada regeneração. Ela não
       recupera o código destruído, não lê o manifesto de injeção e não muda a classificação. É um aceite de
       qualidade limitado, não um vínculo explicado. Nada sai do dado. A consulta 4 do BI (`q_p08_november.sql`) **não** serve de contraprova:
       ela filtra `source_type='shipment'` e o id numérico, que o gerador não grava;
   - para a V5, o giro dentro da faixa declarada.

   **Quando as guardas valem** (RVRB-1-02). São três fases, com o resultado esperado de cada uma:
   - **(i) Controle positivo, antes do ciclo:** rodar as guardas sobre o armazém da `v2.1.0`. Elas **devem
     falhar** e achar os eventos de 17/11. A medida diz quantos acham, quantos são do exercício e quantos a
     quarentena explica. Uma guarda que nunca falhou não prova que pega o F31. A medida dá, em eventos, a parte
     do F31 no antes → depois. A separação por view entre o F31 e a V5 não decorre só dela, e o que não for
     separável é declarado assim;
   - **(ii) Durante o exercício,** sobre o estado que vai ser descartado: a falha é esperada, registrada no diário
     e não impede o passo seguinte. Os *builds* que a prova incremental pede depois de eventos vivos acontecem
     aqui;
   - **(iii) Depois da regeneração:** o `check` integral, com as guardas obrigatórias, é condição de publicação.
     Nenhum *build* do estado publicado acontece antes da regeneração. As descrições (Bloco 3) e o pacote
     (Bloco 4) entram no `dbt-build` da publicação.
5. Uma linha na [Execução Local](docs/execucao_local.md) diz que o `stream-produce` suja o estado publicado e
   que a guarda acusa isso.
6. A revisão integral do Owner sobre o declarativo: `geracao.yml`, a D93 (e o ADR, se houver) e as guardas.

**Item 1, medido em 18/11/2026,** só leitura, sobre o armazém da `v2.1.0`, numa transação `REPEATABLE READ READ
ONLY`. Consultas e saídas ficam em `data/medicoes/reabertura/bloco2/`, fora do Git.
- **O alcance**, pelo `manifest.json`: as três entradas que o produtor alcança são `retail.inventory_movements`,
  `retail.inventory_movements_stream` e `retail.inventory_balances`. Delas descendem `staging`, a `trusted`
  (`inventory_movements` e `inventory_balances`), a `fact_inventory_movement` e três views: P08, P11 e P12. Os
  movimentos alcançam 38 testes, e os saldos, 7.
- **A regra 1** (movimento depois da `as_of_date`, pelo `occurred_at`) acha exatamente **2.200** na fato, todos do
  varejo. É o N da E4 do diário do 5R. O destino quente e o `raw` do Airbyte têm os mesmos 2.200. O legado não
  tem nenhum.
- **A regra 2** (saída por venda sem a remessa dela, pelo `shipment_code` na mesma origem) acha:
  - **984 no varejo**, todos depois do corte. É o número do BI, agora pelo vínculo certo;
  - **13 no legado**, todos antes do corte. Os 13 têm a remessa na quarentena com o código intacto, rejeitada
    em cascata porque o pedido dela foi rejeitado (`PARENT_REJECTED`; remessas 2, 16, 49, 110 e 111).
- **Nenhum caso não demonstrável** na `v2.1.0`, ou seja, a lista da Q72 (d) estaria vazia. A medida se repete
  depois da carga regenerada, porque a injeção muda com o lote.

**Item 3, a V5 medida em memória em 18/11/2026,** pela P11 simulada com a regra do ADR-0052. O *script* é
`data/medicoes/reabertura/bloco2/v5_formas.py`, sobre a medida da V4; as saídas ficam ao lado, fora do Git. Todas
as formas mantêm o lastro da V4: nenhuma saída sem estoque.

| Forma | Varejo: mediana / p90 | Legado: mediana / p90 | Estoque no fim (varejo) |
|---|---|---|---|
| Hoje (`v2.1.0`) | 0,01 / 0,43 | 0,02 / 0,44 | 704.762 |
| Escala ×0,1 / ×0,02 | 0,13 / 0,70 e 0,34 / 1,00 | 0,15 / 0,81 e 0,36 / 0,93 | 70.848 e 24.529 |
| Demanda, de 30 a 180 dias, folga 1,5 | 0,35 a 0,39 / 1,08 a 1,18 | 0,38 a 0,40 / 1,01 a 1,15 | cerca de 20.000 |
| Demanda, 30 dias, folga 1,0 | 0,77 / 3,41, com 22 linhas indefinidas | — | 10.580 |
| **Demanda, 60 dias, folga 1,2 (Q73)** | **0,47 / 1,34**, 1 indefinida em 5.560 | **0,50 / 1,21**, 0 em 277 | 15.224 |

**Implementada em `e237470`**, como pós-passo do gerador depois das remessas (`compras.dimensionar_pela_demanda`).
Ele mantém os sorteios de estrutura e refaz as quantidades da compra, o recebido, o total e o estado da ordem.
Medida em memória sobre o gerador implementado: **varejo 0,46 / p90 1,28; legado 0,48 / p90 1,21**, nenhuma saída
sem lastro, 1 linha indefinida em 5.560 (`v5_implementado_*.txt`).

**As guardas ficam fora da árvore até o *build* do ciclo,** como no 5R: lá, as guardas ficaram "fora da árvore
até a D2" e foram commitadas na F0. Os arquivos de `dbt/` são insumo do pacote, e o pacote só se regenera sobre
o *manifest* de um `dbt-build`, que é proibido antes da regeneração (fase iii). O *patch* é
`data/medicoes/reabertura/bloco2/guardas_dbt.patch`:
- `f31_nenhum_movimento_depois_do_corte` e `f31_saida_por_venda_tem_remessa`;
- o *seed* `f31_legacy_sale_exceptions`, vazio;
- `v5_giro_mediano_dentro_da_faixa`;
- as variáveis `turnover_median_min` e `_max`.

**A fase (i)** foi medida em 18/11/2026. As guardas foram compiladas fora de `dbt/target`, e o SQL foi executado
só para leitura sobre a `v2.1.0`, com o *seed* vazio no lugar (`fase_i_guardas.txt`): **2.200, 984 e 0,02**. As
três reprovam, como devem. O *patch* entra na árvore no passo 4 do Bloco 5, antes do `dbt-build RESET=1`.

A venda é esparsa: 12.224 unidades em 2.926 pares no varejo, cerca de 0,4 unidade por par e trimestre. Por isso
a forma pela demanda satura perto de 0,4 com a folga de 1,5. A medida é aproximada, porque refaz só as
quantidades dos movimentos e não as ordens nem os recebimentos. A implementação refaz os dois, e a guarda da
faixa (Q67) é medida de novo em memória antes do ciclo e no armazém depois dele.

### Bloco 3 — as descrições das relações (F32)

1. Descrever as 123 relações **no dono declarativo de cada grupo**, nunca no derivado (RVRB-1-05):
   - **`raw` (30):** a descrição já existe no `table_meta` dos modelos SQLAlchemy (`models/base.py:51–53`). O
     `_retail__sources.yml` é escrito à mão, mas as colunas dele já são espelho da declaração, escrito por
     `sensitivity.main` (`models/descriptions.py`). O espelho passa a levar também a descrição da tabela;
   - **`raw_legacy` (40):** o `_legacy__sources.yml` é gerado (`legacy/dbt.py::sources_yml`, "Não edite") e só
     emite nome e colunas. O gerador passa a emitir a descrição da tabela: o significado da entidade vem do
     `table_meta`, e o gerador o **qualifica** como relação retida, com as capturas, as ocorrências físicas, os
     valores textuais, os defeitos preservados e a retenção (RVRB-2-03). Copiar o texto sem qualificar
     descreveria errado a relação. Por exemplo, "saldo atual de cada SKU por armazém" não é o grão de
     `raw_legacy.inventory_balances`. O pacote publica a descrição de cada tabela, e não a do agrupamento
     (`models/pacote.py:239–247`), então a qualificação tem de estar na tabela;
   - **`staging`, `trusted`, `snapshots` e `quarantine` (53):** no `.yml` de cada modelo, que é declaração. Os
     modelos descrevem o grão e o papel.
2. Estender `tests/test_descricao.py` às relações, com **teto zero** e uma mensagem que nomeia cada relação
   sem descrição. A guarda inventaria também as fontes e os objetos materializados sem declaração no `.yml`.
3. Revisão integral do Owner: é declarativo, e são até 123 textos. É o maior volume da fase (risco R14). As 70
   de `raw` e `raw_legacy` saem de textos que já existem na declaração, e a revisão confere o transporte.

**O Bloco 3 fica fora da árvore até o *build* do ciclo** (Owner, 18/11/2026), pelo mesmo motivo das guardas do
Bloco 2: as três formas de descrição escrevem em `dbt/` (o espelho de `sensitivity.main`, o gerador do legado e
os `.yml` dos modelos), e o carimbo do pacote só se refaz com um `dbt-build`, proibido antes da regeneração. O
*patch* é `data/medicoes/reabertura/bloco3/descricoes.patch` e leva também a guarda de teto zero. Antes de
congelá-lo, ele é aplicado numa cópia de trabalho temporária, com a suíte offline (só o teste do carimbo pode
reprovar) e o dbt compilado fora de `dbt/target`. O resultado fica ao lado do *patch*. As alternativas
descartadas foram dividir o bloco, deixando o código na árvore e os `.yml` no *patch*, porque os testes de
sincronia do gerador acusam a diferença, e uma *branch* sem *merge*, porque cada *commit* nasceria com o
`check-offline` vermelho.

**Feito em 18/11/2026,** fora da árvore. O *patch* aplica depois do das guardas. A validação e os
SHA-256 estão em `data/medicoes/reabertura/bloco3/validacao.md`, e os textos para a revisão em
`descricoes_para_revisao.md`, ao lado:
- **`raw` (37):** o `table_meta` abre a descrição da tabela. As 7 que já tinham nota (o papel da réplica, o
  ADR) a mantêm depois dele. Na tabela, o espelho é **conferido, não escrito**: `descriptions.table_texts`
  dá o começo esperado, e a falta ou a divergência é problema da derivação, que reprova o `--check` com o
  texto na mensagem. A nota é de quem a revisa, e um `table_meta` que mudar pede que alguém a releia
  junto. O grão é o da origem: medido só leitura, `raw` tem uma linha por `id` nas 5 tabelas conferidas,
  nos três modos do Airbyte;
- **`raw_legacy` (40):** um molde no gerador (`descriptions.legacy_relation_text`). O texto é a relação
  retida (ocorrência física por captura, valores como texto, defeitos preservados, retenção permanente), e
  a entidade de origem vem só como referência, "o grão não é o da entidade de origem";
- **as 53 escritas à mão:** 18 foram promovidas do `_derived.yml` ao `.yml` à mão, com as colunas como a
  derivação as escreve, e os dois `_derived.yml` saíram porque ficaram vazios. Os 29 de `trusted` declaram
  o grão com `source_system`, porque todos empilham as duas origens. A exceção é `geographies`, que é
  distinta por país, UF e cidade;
- **a guarda** `test_relacoes_sem_descricao_por_camada_no_teto`, com teto zero, sobre o banco. O controle
  positivo, com o manifesto da base, reprova nomeando as 123.

**Correção no *patch* das guardas do Bloco 2,** achada pela suíte do *worktree*: a guarda
`f31_nenhum_movimento_depois_do_corte` chama `meia_noite`, e o contador de `test_vigencia_em_utc` passa de
18 a 19. O *patch* passou a levar a atualização do contador. A versão aprovada ficou guardada ao lado.

**O Owner, em 18/11/2026:** o Bloco 3 está aprovado sem a revisão integral, que ele declarou que não poderá
fazer (item 3), e a correção do *patch* das guardas está aceita. A falta de `source_system` na quarentena das
entregas virou o **F35**, para ser corrigida na melhor forma.

**O F35, num *patch* próprio,** `bloco3/f35_quarentena_origem.patch`, que aplica depois do das descrições e vira
o seu próprio *commit*:
- a coluna `source_system`, a primeira, lida de `trusted.shipments`, com o texto da convenção, e a unicidade em
  `(source_system, shipment_id)` (`dbt_utils.unique_combination_of_columns`, como nas dimensões). É o
  ADR-0039: a origem existe em toda tabela que recebe registros de mais de um sistema;
- a descrição da relação passa a dizer o grão com a origem;
- o comentário de `entrega_projetada_tem_evento_no_livro`, que lia `trusted.shipments` "porque ela não guarda a
  origem", passa a dizer que confere a regra e não a cópia. O teste não muda;
- formas descartadas: prefixar o código com a origem, que mudaria a chave natural, e só documentar, que
  deixaria a linha ambígua;
- a linha `prevista` em Consumidores §5, porque é mudança de esquema numa relação publicada. Ela passa a
  `feita` depois do *build* do ciclo.

Validado sem `compile`. O `--check` da derivação rodou sobre uma cópia do manifesto compilado, só no
*worktree*, com o `raw_code` do modelo e a coluna nova no SQL compilado. Deu 3.020 colunas e nenhum arquivo
desatualizado, ou seja, a coluna escrita à mão é a que a derivação escreveria. O `parse` registra o teste
composto, e a suíte *offline* tem as mesmas 3 falhas esperadas (`validacao.md`).

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

**Feito em 18/11/2026, na árvore** (`198315c`). O Bloco 4 não toca `dbt/`, e o carimbo prende só os insumos do
dbt. Por isso o pacote se regenera sobre o *manifest* da `v2.1.0` (`make catalog → make test → make catalog`):
- **F34:** `relations.*.primary_key` e `foreign_keys` saem de `data_types.declared_primary_keys` e
  `declared_foreign_keys`, a regra da macro, agora num só lugar, que `tests/test_chaves.py` também usa. Deu **26
  PKs e 58 FKs**, e só `analytics` tem chave. Os **76** `relationships` têm `references_relation` e
  `references_column`, 58 em `analytics` e 18 em `staging`. Um destino que não resolve é recusa;
- **UQ-19:** `view_audits.*.checks` (26 casos do `pytest`: as 16 referências e as 10 populações) e
  `data_tests` (1: a população da P13 é o teste singular `p13_conta_toda_remessa_entregue`, e o resultado dela
  está em `tests`, não em `checks`). O campo `data_tests` não estava no plano; ele nasceu porque a guarda do
  gerador recusou o id da P13 em `checks`, e a linha `prevista` de Consumidores §5 foi atualizada. Um id que o
  JUnit não tem é recusa;
- **UQ-18:** a especificação diz que a chave de uma view é `grain` + `identity` de `view_rules`, e que
  `relations.*.grain` é `null` nas views de propósito. `tests/test_chave_das_views.py` confere no armazém: as 16
  views, **0 combinações repetidas** (medido antes, só leitura);
- **F33:** a nota de `registro_fase_gcp` aponta o custo lido em 16/11/2026, e a entrada nova `custo_gcp` aponta a
  Capacidade §2.14;
- **o resultado:** `make test` deu 1.814 passados e 19 pulados. Dos pulados, 16 pedem `GCP_TESTES=1`, e 3 têm condição local: a carga em banco efêmero (`make test-carga`), o reprocessamento da fato (`FATO=1`) e a prova entre capturas, sem mutação no diário. Esses 3 não rodaram (RVRB4-1-01), e o `check-offline`
  passou. No pacote, as únicas mudanças são os campos novos e os 29 casos novos em `checks`, nenhum com falha. Os
  três *patches* fora da árvore continuam aplicando em sequência sobre `198315c`.

As linhas `prevista` do F34 e do UQ-19 passam a `feita` só depois do *build* do ciclo, com o `invocation_id`.

### Bloco 5 — o ciclo

**A adaptação, proposta em 18/11/2026,** está em `data/medicoes/diario_reabertura.md`, fora do Git (o Owner:
"preparar e parar"). Ela traz:
- o estado de partida, medido;
- os parâmetros (`LIMITE` 2.200, `QUANTAS` 250, o prazo de 900 s da D63, a geração do `MAINT`);
- a H2 desta geração, medida em memória: 26 remoções no legado e zero reaparições, que viram a Q74;
- o corte de recuo sobre `4137dc7`, o cursor na B6 e as três fases das guardas;
- a parada da Q72 e os oráculos linha a linha;
- dois *scripts* só leitura, `capturar_views.py` e `residuo_zero.py`, ensaiados sobre o estado de partida.

O ciclo começa com a revisão da adaptação sem bloqueio, a Q74 respondida e o Owner presente para os `FORCE`.

Mesma forma do ciclo do Bloco 5R, com um diário próprio (`data/medicoes/diario_reabertura.md`).

**Dois `FORCE` diferentes** (RVRB-1-01). Um é a **autorização de descarte**: o `stream-down FORCE=1` apaga os
tópicos e o *slot* de replicação, o `stream-reset-sink FORCE=1` esvazia o destino quente, e o
`seed-data FORCE=1` e o `seed-legacy FORCE=1` trocam as origens (diário B1 a B4). Cada um é confirmado pelo
Owner no passo em que roda, como no 5R. O outro é o **desvio do *preflight* de memória** (`CLAUDE.md` §5), que
continua proibido sem a liberação da máquina pelo Owner. Os dois nunca se confundem no diário.

#### A adaptação do ciclo (antes de qualquer passo destrutivo)

Uma subseção do diário, revisada pelo outro agente **antes** do primeiro descarte, como a adaptação do 5R
(RVRB-1-06). Ela fixa:
- **os parâmetros:** `LIMITE`, a semente, o `QUANTAS` da duplicação, o prazo da D63 e as épocas do livro de
  capturas (qual se encerra, qual abre e com que linha de base);
- **o corte de recuo:** um pacote de recuperação do estado de partida, com SHA-256 e cópia fora do *checkout*,
  **antes** do exercício (o "pre-bloco5r" do 5R, A3);
- **o cursor do produtor** (Q71): o estado de partida tem o cursor de 17/11 (2.200 emitidos), e a regeneração
  descarta os eventos que ele conta. O tratamento escolhido acontece **antes** de embalar o estado final, porque
  `ARTEFATOS` leva o cursor no pacote, e a restauração o traria de volta;
- **os oráculos de cada passo** e o que cada falha esperada significa, pelas três fases das guardas
  (Bloco 2, item 4);
- **a parada da Q72**, se a resposta for a (d): o inventário dos casos não demonstráveis do legado, medido
  depois da carga, e a aprovação da lista pelo Owner antes da fase (iii);
- **as provas que se mantêm,** cada uma com o passo em que roda:
  - a T3 (`memory-oracle`) antes de encerrar a época e depois do ciclo;
  - a comparação H2, com as remoções e reaparições aceitas;
  - a T4 depois dos tratamentos;
  - a DAG real;
  - a T3 e a procedência `verified` depois da restauração, e o catálogo do estado final;
  - os registros de tratamento (`ledger-treatment`), inclusive depois de *build* que falha;
  - a comparação dos dois caminhos (C4 e E10);
  - a medida do conteúdo das duas origens antes da carga (H1 e B5);
  - o H2 contra o estado real e o manifesto anterior congelado. As aceitações de remoção e de reaparição são
    **desta geração**, e as da Q50 não valem para ela;
  - a publicação de *commit* limpo e o pacote de recuperação renovado sobre o dado novo (G3 a G9 do 5R), com a
    identidade do corte de recuo fixada.
- **o que não se prova na base publicada** (abaixo), e onde fica provado.

#### Os passos

1. **O antes:** a captura das 16 views, numa transação `REPEATABLE READ READ ONLY`, sobre o armazém da
   `v2.1.0`, com SHA-256 de cada saída. Em seguida, o **controle positivo** das guardas, fase (i).
2. **O exercício de *streaming*, na forma (e),** sobre o estado que vai ser descartado: o produtor, a
   duplicação, a espera da D63 com o sinal novo, a observação da V6, a sincronização e o `dbt-build` com os
   eventos vivos (a prova incremental) e a comparação dos dois caminhos. As guardas falham, fase (ii), como
   esperado.
3. **O descarte**, na ordem do 5R:
   1. `stream-down FORCE=1`: os tópicos e o *slot* (B1);
   2. `stream-reset-sink FORCE=1`: o destino quente vazio, conferido (B2);
   3. `seed-data FORCE=1` e `seed-legacy FORCE=1`: as duas origens regeneradas pela declaração nova (B3, B4),
      e o oráculo das fontes (B5);
   4. `sync-airbyte RESET=1`: o `raw` relido da origem nova, com o cursor descartado (C2).
4. **A publicação sem produtor:** o *snapshot* do CDC entrega o livro regenerado (C3) e os dois caminhos são
   comparados (C4). Depois, a captura do legado, os três *patches* aplicados, um *commit* cada (as guardas
   do Bloco 2, as descrições do Bloco 3 e o F35), o `dbt-build RESET=1` (D3), que refaz o SCD e os incrementais,
   as guardas na fase (iii), a procedência `verified`, o `check`, a DAG e a restauração (com a V7).
5. **A conferência de resíduo zero**, antes do aceite. Nenhum movimento com `occurred_at` depois da `as_of_date`
   no destino quente, no `raw`, no *staging*, no `trusted` e na fato; os saldos de `analytics`, com a população
   declarada (RVRB-2-04): **no varejo**, conjunto de chaves e saldos iguais aos da origem regenerada, no corte
   comum; **no legado**, a população apta da captura selecionada, com as divergências explicadas pelo tratamento
   corrente (`trusted/inventory_balances.sql`, `saldo_reconstruido_confere_com_a_projecao.sql`). O par armazém 1
   × variante 30 da V4 é o exemplo: a abertura dele é rejeitada, e o livro apto começa na versão 2; o cursor do produtor no estado que a Q71 escolher. **A memória mantida** é a do pacote
   de recuperação (`recovery/pacote.py:42–49`): `raw_legacy`, `governance`, `snapshots` e `quarantine`. O `raw`
   e o `analytics` não são memória e se refazem da origem.
6. **O depois:** a mesma captura das 16 views, e a diferença por view publicada em Consumidores §5 (linhas e
   somas antes e depois, por view). A comparação usa as chaves medidas e as regras de aditividade declaradas,
   sem somar taxas nem denominadores repetidos.
7. As guardas novas passam no armazém. A P11 é medida contra a meta da V5.

#### O que a base publicada não prova

É o custo aceito da forma (e). Sem produtor sobre a base nova, a publicação prova o *snapshot* do CDC e a
reconstrução, mas **não** prova, nessa base:
- a entrega de eventos vivos;
- as transições de alerta;
- a parcela quente da P12;
- o avanço incremental depois de eventos vivos.

Os quatro ficam provados no passo 2, sobre a base descartada, com o diário como evidência, e o aviso aos
consumidores diz isso. Combinar a (e) com a (b) provaria os quatro na base publicada, ao custo de uma
restauração a mais. Não é recomendada agora.

Se a Q64 ficar com outra forma, os passos 2 a 4 voltam à ordem do Bloco 5R.

### Bloco 6 — os textos depois do ciclo

UQ-17, UQ-20, a ordem de Consumidores §5 (Q70) e o cabeçalho dos Achados.

### Fechamento

- `make check` verde; catálogo, dicionário, linhagem e pacote regenerados.
- A revisão por outro agente, por bloco, e a do fechamento.
- O aceite do Owner e a *tag* (Q69).
- Um aviso único aos três consumidores, com a *tag* e Consumidores §5.
- O que **não** foi provado continua declarado: o BigQuery (L9) e o que a base publicada não prova sobre o
  *streaming* (Bloco 5).

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
| Resíduo do exercício no estado publicado | A sequência de descarte explícita e a conferência de resíduo zero (Bloco 5, passos 3 e 5). As guardas (fase iii) falham o `check` |

---

## 5. Decisões pedidas ao Owner — rodada 1

A numeração continua a do plano da base dos consumidores, para que uma `Qnn` citada em Consumidores §5
não seja ambígua.

| # | Pergunta | Opções | Recomendação |
|---|---|---|---|
| Q64 | A forma da correção do F31 (D93) | **(e)** O exercício roda **antes** da regeneração, sobre o estado que ela vai descartar. Depois de regenerar, publica-se sem produtor. Uma guarda no estado publicado falha o `check` se aparecer movimento depois da `as_of_date` ou venda sem pedido. **(a)** O produtor marca a origem do evento como exercício, e as views e os saldos publicados o excluem por regra declarada (contrato do evento e ADR). **(b)** Depois do exercício, a origem e o armazém voltam ao corte de antes dele, pela restauração. **(c)** O produtor emite eventos coerentes com o domínio, com venda ligada a pedido. **(d)** O produtor deixa de emitir venda: não resolve os saldos nem o custo dos outros tipos. **Descartadas (Owner perguntou, 17/11):** apagar as linhas ou trocar células, porque o livro é *append-only* por contrato, a alteração ou exclusão na origem atravessa o transporte como mensagem de CDC e o `envelope.py` a recusa com `ContratoViolado` (`u`, `d` e `t`), o que para o *pipeline*, o histórico do `inventory_balances` (`dedup_history`) e as capturas certificadas a registrariam, e as regras 3 e 4 do `CLAUDE.md` a proíbem; e o estorno (linhas compensatórias), que devolve o saldo mas não tira a venda bruta da P11 nem o custo da P08, e deixa as datas depois da `as_of_date` | **(e)**, se a medida do Bloco 2, item 1, e a conferência de resíduo zero do Bloco 5 confirmarem que a sequência de descarte tira do armazém os eventos do exercício (a fato de movimentos é incremental). Resolve os saldos sem tocar em nenhuma linha, não muda o contrato do evento e não pede ADR de tratamento de dados. A guarda torna visível qualquer exercício futuro sobre o estado publicado. Fica declarado na D93 que a (c) é o caminho se um dia o produtor simular operação continuada de verdade (intenção da fase GCP). Se a medida não confirmar, a (b) |
| Q65 | A D63 | As opções (a), (b) e (c) das Pendências | **(a)** |
| Q66 | A D64 | As opções (a) e (b) das Pendências | **(a)** |
| Q67 | A meta do giro da V5 | **(a)** Uma faixa declarada para a mediana trimestral da P11, a fixar com a medida em memória. **(b)** Só "maior que hoje", sem faixa | **(a)**. A faixa é escolha sua: a proposta parte da medida em memória, e não de um número de fora |
| Q68 | Medir o antes → depois das 16 views neste ciclo | Sim / Não, como a Q63 | **Sim**: os dois consumidores que esperam vão comparar valores, e o diff daqui evita que cada um o refaça |
| Q69 | A *tag* desta fase | `v2.2.0` / `v2.1.1` | **`v2.2.0`**: o dado muda |
| Q70 | A ordem de Consumidores §5 | Corrigir a ordem / Corrigir e guardar com teste a ordem por data | **Corrigir e guardar** |
| Q71 | O cursor do produtor (`emitidos_acumulados` 2.200 de 17/11, mais os do exercício), depois do descarte | **(a)** Guardado com SHA-256 no diário e removido: o estado publicado parte do zero, como a Q52. **(b)** Mantido: o próximo exercício continua a sequência, mas o cursor conta eventos que não estão no livro | **(a)**: depois do descarte, o cursor descreveria um livro que não existe mais, e o pacote de recuperação o levaria junto |
| Q72 | A regra "toda venda tem remessa" no legado, onde a injeção pode destruir o código da remessa (a 47) e nenhuma tabela guarda o original (RVRB-2-01) | **(a)** Estrita no varejo, onde o produtor escreve. No legado, não reprova o `check`: é medida nas fases (i) e (iii), com cada caso listado: explicado pela quarentena com o código intacto, ou não demonstrável. O que não for demonstrável vira achado ao Owner. **(b)** Estrita nas duas origens, com o não demonstrável como falha: a injeção deliberada reprovaria o `check` a cada regeneração. **(c)** Estrita nas duas, e o tratamento do legado passa a guardar o vínculo polimórfico do movimento com a remessa rejeitada: é tratamento de dados novo e pede ADR. Ler o manifesto de injeção na guarda foi descartado, porque é usar o oráculo como dado. **(d)** Estrita no varejo. No legado, a ausência explicada pela quarentena corrente passa, os casos não demonstráveis entram numa lista de exceções desta geração aprovada pelo Owner, com identidade, captura, catálogo, impressão do tratamento e evidência congelada, e qualquer caso fora da lista reprova o `check`. Custo: a lista é refeita e reaprovada a cada regeneração, com uma parada para o Owner no Bloco 5 entre a carga e a fase (iii) | **(d)**: é a única sem tratamento novo em que um caso novo no legado reprova o `check`, e a escolha do Owner foi a solução mais robusta. A (a) é a mais leve e deixa passar caso novo, que só é anotado. A (c) fica para se a lista crescer a ponto de pedir o vínculo no tratamento |


### Respostas do Owner (17/11/2026)

A Q64 foi respondida antes, pela forma (e). As Q65 a Q72 foram respondidas em 17/11/2026, todas pela recomendação. A Q73 e a faixa da Q67 vieram em 18/11/2026, com a medida da V5:

| # | Resposta |
|---|---|
| Q64 | **(e)**: o exercício antes da regeneração, a publicação sem produtor e as guardas no estado publicado |
| Q65 | **(a)**, na forma do Bloco 1: a confirmação por janela concluída, a entrega confirmada e a espera pelo que a execução inseriu |
| Q66 | **(a)**: a chave em base64 seguro para URL nos dois lugares, com teste, e a troca ao recriar o Airflow |
| Q67 | **(a)**, fixada em 18/11/2026 depois da medida em memória: a mediana trimestral do giro da P11 entre **0,30 e 0,80**. A guarda mede a P11 publicada, com as duas origens juntas, porque a view não tem a origem; a medida em memória confere cada origem dentro da faixa |
| Q68 | **Sim**: o antes → depois das 16 views, medido e publicado por view |
| Q69 | **`v2.2.0`** |
| Q70 | **Corrigir e guardar** com teste a ordem por data |
| Q71 | **(a)**: o cursor guardado com SHA-256 no diário e removido antes de embalar o estado final |
| Q73 | **Pela demanda** (18/11/2026): cada compra cobre as saídas do par nos 60 dias seguintes, a abertura cobre os primeiros 60 dias, e a folga do lastro cai de 1,5 para 1,2 (medida abaixo, Bloco 2) |
| Q72 | **(d)**: a lista de exceções do legado desta geração, num *seed* versionado aprovado pelo Owner, e caso novo reprova o `check` |
| Q74 | **Aceita pelo Owner em 18/11/2026**: aceitar na T3 as 26 remoções de `inventory_movements` que a regeneração faz no legado, medidas em memória (zero reaparições; a memória de exclusão passa de 67 a 93 chaves). A recomendação é aceitar, porque é a consequência da V5. Proposta e medida na adaptação do ciclo (`data/medicoes/diario_reabertura.md`, §3) |

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
- **O item 16 (F34)** entrou depois do objeto da rodada, a partir do canal do `gdados`.

**Aplicada em 17/11/2026.** A coluna Situação está no relatório. Onde cada achado entrou:

| # | Veredito | Onde entrou |
|---|---|---|
| RVRB-1-01 | bloqueante | Bloco 2, item 1 (a regeneração sozinha não tira os eventos); Bloco 5: os dois `FORCE`, o passo 3 (a sequência de descarte) e o passo 5 (a conferência de resíduo zero e o alcance da memória mantida); Riscos |
| RVRB-1-02 | bloqueante | Bloco 2, item 4: as três fases das guardas, com o controle positivo sobre a `v2.1.0` |
| RVRB-1-03 | ajuste | Bloco 2, item 4: o vínculo por `source_type='sale'` e `shipment_code`, a quarentena classificada à parte, o `occurred_at` |
| RVRB-1-04 | ajuste | Bloco 1, D63: o sinal pelo fechamento da última janela, o zero legítimo, o prazo como falha, a execução sem produtor |
| RVRB-1-05 | ajuste | Bloco 3: o dono declarativo de cada grupo. Conferido: o `_retail__sources.yml` é escrito à mão, com as colunas espelhadas da declaração por `sensitivity.main`; o `_legacy__sources.yml` é gerado |
| RVRB-1-06 | bloqueante | Bloco 5: a adaptação do ciclo, revisada antes do primeiro descarte, e o que a base publicada não prova; Fechamento |
| RVRB-1-07 | ajuste | Nos avisos, fora do Git. O do `gdados` foi corrigido por `resposta_gdados_20261117b.md`. O do `nl_sql` foi corrigido no lugar: nenhum texto do `nl_sql` cita o `aviso_nl_sql_20261117b.md` |
| RVRB-1-08 | ajuste | Q64: a justificativa do CDC |

**Achado do autor, fora da rodada:** o cursor do produtor (Q71). O estado de partida tem o cursor de 17/11, e o
descarte tira do livro os eventos que ele conta.

### Rodada 2 — codex2, sobre `9c3f698` (17/11/2026)

Relatório: `data/medicoes/reabertura/codex2_plano_r2.md`, fora do Git. **Conclusão do Codex:** nada bloqueia
o Bloco 0. A forma (e) continua viável. RVRB-1-01, 02, 06, 07 e 08 estão resolvidos; 03, 04 e 05, em parte. A
análise da Q71 está correta, e nenhum outro estado do exercício atravessa o descarte. A situação de cada achado
está no relatório. **Aplicada em 17/11/2026:**

| # | Veredito | Onde entrou |
|---|---|---|
| RVRB-2-01 | bloqueante | Bloco 2, item 4: o caso da remessa 47, sem junção possível. A forma da regra no legado vai ao Owner, Q72. O Bloco 5 espera a resposta |
| RVRB-2-02 | ajuste | Bloco 1, D63: a confirmação por janela concluída, a entrega confirmada e a leitura pelo medidor. Destino durável novo volta ao Owner |
| RVRB-2-03 | ajuste | Bloco 3: a descrição de `raw_legacy` qualificada pelo gerador como relação retida |
| RVRB-2-04 | ajuste | Bloco 5, passo 5: a população da igualdade dos saldos, por origem |

Também vieram das verificações: na adaptação, o H1 e o B5, o H2 desta geração, o *commit* limpo e o pacote
renovado; o cursor tratado antes do pacote; e a atribuição F31 × V5 sem prometer mais que a medida dá.

### Rodada 3 — codex2, sobre `66d898e` (17/11/2026)

Relatório: `data/medicoes/reabertura/codex2_plano_r3.md`, fora do Git. **Conclusão do Codex:** nada bloqueia
o Bloco 0. RVRB-2-01, 03 e 04 estão resolvidos; o 02, em parte. As verificações confirmam que o produtor só
escreve no varejo, que a (a) da Q72 respeita a regra 4, e que H1/B5, H2, o *commit* limpo, o pacote renovado,
a Q71 e a atribuição F31 × V5 estão corretos. **Aplicada em 17/11/2026:**

| # | Veredito | Onde entrou |
|---|---|---|
| RVRB-3-01 | bloqueante | Bloco 1, D63: a espera pela cobertura de todos os pares (chave, janela) do corte, pela contagem esperada calculada do livro, inclusive janelas anteriores e painéis tardios, e a contraprova do par retido |
| RVRB-3-02 | ajuste | Bloco 2, item 4, e Q72: a opção (d), uma lista de exceções desta geração aprovada pelo Owner, com reprovação de caso novo, agora a recomendada; a parada dela na adaptação do ciclo |

### Rodada 4 — codex2, sobre `118b2b3` (17/11/2026)

Relatório: `data/medicoes/reabertura/codex2_plano_r4.md`, fora do Git. **Conclusão do Codex:** nada bloqueia
o Bloco 0. RVRB-3-02 está resolvido, e a (d) da Q72 cabe num *seed* versionado. RVRB-3-01 está resolvido em
parte: a atribuição às janelas é reproduzível do livro (60 s, alinhadas à época Unix, por `occurred_at`), as
duplicatas não entram na expectativa, e o atraso além da tolerância dá falha pelo prazo. **Aplicada em
17/11/2026:**

| # | Veredito | Onde entrou |
|---|---|---|
| RVRB-4-01 | bloqueante | Bloco 1, D63: a expectativa é o inserido por esta execução, com marca do *sink*; a contraprova do destino preenchido; o atraso além da tolerância. Bloco 2, Q72 (d): a lista num *seed* versionado |

### Rodada 5 — codex2, sobre `b10907c` (17/11/2026)

Relatório: `data/medicoes/reabertura/codex2_plano_r5.md`, fora do Git. **Nenhum achado aberto.** Nada bloqueia o
Bloco 0. O Bloco 5 espera só as respostas Q65 a Q72 e os pré-requisitos já declarados. O RVRB-4-01 está
resolvido, e o conjunto inserido pode ser registrado sem coluna nova no destino quente. A frase do *seed* da Q72
(d) está correta. **A revisão do plano está encerrada.**

### Bloco 2 — rodada 1 do codex2, sobre `127c118` (18/11/2026)

Relatório: `data/medicoes/reabertura/codex2_bloco2_r1.md`, fora do Git. **Nada bloqueia o Bloco 3.** O codex2
reproduziu a P11 simulada sobre o gerador implementado (varejo 0,464 / p90 1,277; legado 0,476 / p90 1,211). Ele
também conferiu, sem divergência:
- a demanda contra o livro;
- a invariante 6, a divisão dos lotes e as devoluções;
- o determinismo;
- o caminho do legado;
- as guardas, com a sintaxe das três consultas validada nos dois dialetos;
- o *patch* fora da árvore, compatível com a regra 3 até o ciclo.

As lacunas de cobertura em fatores muito pequenos são as mesmas do gerador anterior, ou seja, não são regressão
da V5. O único achado, RVB2-1-01, foi um ajuste de texto na Geração de Dados §3, e foi aplicado.

**Revisão integral do Owner feita em 18/11/2026, aprovada:** o `geracao.yml` (`e237470`), o *patch* das guardas e
a D93. O Bloco 2 está fechado.


### Bloco 3 — rodada 1 do codex2, sobre os *patches* em `429d94b` (18/11/2026)

Relatório: `data/medicoes/reabertura/codex2_bloco3_r1.md`, fora do Git. O codex2 reconstruiu os dois *patches* só
em memória e conferiu 130 textos mudados, 18 promoções sem nenhuma outra mudança nas entradas e nenhum SQL de
modelo alterado. Conferiu também os 37 prefixos de `raw`, os 40 textos de `raw_legacy`, a guarda e a correção
18 → 19. Pelo leitor do pacote, em memória, deu 0 lacunas de relação. Três textos estavam errados, e erro em
declaração é bloqueante. **Aplicada em 18/11/2026**, no `descricoes.patch` regenerado:

| # | Veredito | Onde entrou |
|---|---|---|
| RVB3-1-01 | bloqueante | `rejected_shipment_deliveries`: o teste acusa cada remessa, salvo a do legado explicada pela quarentena (Q62), e não "falha se ela deixar de estar vazia" |
| RVB3-1-02 | bloqueante | `product_skus`: o valor atual, uma linha por SKU e origem; `dim_product` lê as versões de `scd_product` e tem o grão da versão |
| RVB3-1-03 | bloqueante | `customers`: o ativo conta de `as_of_date`, e a recorrência, da primeira compra |
| RVB3-1-04 | ajuste | Bloco 3: o "Falta" deixa de listar a correção das guardas, que está no *patch* e foi aceita pelo Owner |

### Bloco 3 — rodada 2 do codex2, sobre `eecbc91` (18/11/2026)

Relatório: `data/medicoes/reabertura/codex2_bloco3_r2.md`, fora do Git. **Nenhum achado novo, e nada bloqueia o
Bloco 4.** Os três textos da rodada 1 foram corrigidos sem divergência nova, o RVB3-1-04 foi tratado, e a forma
do F35 preserva a identidade da remessa com a origem, sem mudar os valores nem a regra da Q62. Os SHA-256 dos
três *patches* foram conferidos de forma independente. **O Bloco 3 está fechado**, fora da árvore até o passo 4
do Bloco 5.

### Bloco 4 — rodada 1 do codex2, sobre `5656eb0` (18/11/2026)

Relatório: `data/medicoes/reabertura/codex2_bloco4_r1.md`, fora do Git. **Nada bloqueia o Bloco 5.** A publicação
dos campos novos sobre os artefatos da `v2.1.0` é legítima sob o carimbo: os insumos do dbt não mudaram, e o
manifesto, o carimbo e o pacote concordam. **Aplicada em 18/11/2026:**

| # | Veredito | Onde entrou |
|---|---|---|
| RVRB4-1-01 | ajuste | Bloco 4: a discriminação dos 19 pulados, 16 de GCP e 3 locais, que não rodaram |

**O Bloco 4 está fechado.**

### Bloco 5 — a adaptação do ciclo, rodadas 1 a 3 do codex2 (18/11/2026)

Relatórios: `data/medicoes/reabertura/codex2_adaptacao_r1.md` a `_r3.md`, fora do Git. A adaptação está em
`data/medicoes/diario_reabertura.md`, na revisão 4.

| # | Veredito | Onde entrou |
|---|---|---|
| RVAC-1-01 | bloqueante | N e K medidos depois da E4; K = C0 + N nas esperas, na E6, na E10 e na B2; a fase (ii) espera 2.200 + N |
| RVAC-1-02 | bloqueante | D5: `residuo_zero.py` reconstrói os saldos de `analytics` pelas dimensões, contra a origem no varejo e contra o livro apto no legado |
| RVAC-1-03 | bloqueante | G7b: a T3, a procedência e o catálogo depois da restauração, antes da promoção |
| RVAC-1-04 | bloqueante | E5b (a parcela quente da P12) e E7 (as transições de alerta) antes da B1; o que não ocorrer volta ao Owner |
| RVAC-1-05 | ajuste | `q72.sql` com o recorte do tratamento corrente |
| RVAC-1-06 | ajuste | Com a lista da Q72 não vazia, parada antes da F3 |
| RVAC-1-07 | ajuste | O oráculo do corte de recuo separa as fontes da memória |
| RVAC-2-01 | bloqueante | A base dos alertas na E2b, delimitada por *offset* (`alertas_delimitados.py`) |
| RVAC-2-02 | ajuste | G7b com o `HEAD` que executou a G7; G7c fecha o *diff* de execução |
| RVAC-2-03 | ajuste | E5b: a localidade só nas colunas de saldo; a parcela quente pelas colunas do caminho quente |
| RVAC-3-01 | ajuste | O leitor de alertas reprova também por erro de leitura |

**A rodada 3 não achou bloqueio técnico** para iniciar o ciclo com a Q74 respondida e o Owner presente.
