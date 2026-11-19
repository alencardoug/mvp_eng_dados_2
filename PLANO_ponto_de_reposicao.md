# Plano — o ponto de reposição derivado da demanda (F36)

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 18/11/2026; rodadas 1 a 4 de revisão aplicadas (§7); Q75, Q76, Q77 e Q79 respondidas pelo Owner (§5); a D95, as amostras do `gdados`, incluída pelo Owner em 19/11/2026 (item 11). Nada foi executado além das medidas de leitura do §3 |
| Origem | O [F36](docs/achados_nl_sql.md#f36--o-ponto-de-reposição-fixo-deixa-de-distinguir-com-o-estoque-da-v5--gravidade-média), achado no ciclo da reabertura; a D94, decidida pelo Owner em 18/11/2026 ([ADR-0057](docs/adr/0057-ponto-de-reposicao-pela-demanda.md)); o pedido do Owner, na mesma conversa, de abrir a fase própria |
| Base | `6e664c7`, sobre a `v2.2.0` (`f5a5173`) |
| Consumidores durante a fase | O `gdados` recebeu o aviso da `v2.2.0` pela caixa de correio e segue contra ela. Os avisos da `v2.2.0` ao `bi-como-codigo` e ao `nl_sql` ficam **segurados** e saem no fim desta fase, um por consumidor, já com a *tag* nova (Owner, 18/11/2026). Nenhuma janela de leitura do armazém é aberta enquanto o ciclo do Bloco 3 durar |

Este plano não redecide o ADR-0057. Ele ordena a implementação e traz, no §5, as decisões que o ADR não cobriu.
O conteúdo de cada assunto continua no seu dono: o ADR, o glossário, o `.yml`, Streaming, Governança,
Consumidores e os Achados.

---

## 1. O escopo

| # | Item | Muda o dado? | Bloco |
|---|---|---|---|
| 1 | **O modelo do ponto** (Q75): uma linha por par **natural** (origem × armazém × SKU), com a venda de 365 dias somada através de todas as versões do produto, a demanda diária, o prazo, a margem e o ponto, ancorado no último movimento da fato. As variáveis `reorder_lead_time_days: 28`, `reorder_safety_days: 14` e `reorder_demand_window_days: 365` no `dbt_project.yml`, com a origem da medida no comentário. Sai a `reorder_point_units` | O valor da P12 | 1 |
| 2 | **A P12 lê o ponto do modelo.** `reorder_point` passa a ser o do par, e o filtro `quantity_available < reorder_point`. O resto da view não muda, e **o esquema dela também não**: as mesmas colunas, com os mesmos tipos | O valor | 1 |
| 3 | **A referência independente da P12** (`tests/auditoria/skus_below_reorder_point.sql`) calcula o ponto sozinha, pelos três parâmetros e pela âncora da fato fria, sem ler o modelo. O carregador comum (`tests/test_auditoria_das_views.py:57–62`) passa os três parâmetros novos e conserva os outros | Não | 1 |
| 4 | **O alerta do *streaming*.** Sai o `alerta.limiar_de_unidades` do `fluxo.yml`. O **lançador** lê uma fotografia do ponto de cada par do varejo (`source_system = 'retail'`, chaveada por `(warehouse_id, product_variant_id)`) e a entrega ao `AcumularSaldoEAlertar` pelo construtor. Todas as instâncias recebem a mesma, e ela é fixa enquanto a execução durar. A fotografia é guardada no diretório da execução com SHA-256 e contagem. O par ausente dela tem ponto zero; **a relação ausente, ilegível ou vazia faz o lançamento falhar**, salvo no modo da Q79. O corte D62 do saldo não muda. O alerta publica o ponto do par no campo `limiar`. O `cli.py` (`stream-alerts`) deixa de supor um limiar único. **O modo de carga** percorre a cadeia inteira: `Makefile::medir` → `docker/medir.sh` → `Makefile::stream-run` → `streaming/cli.py::comando_pipeline` → `pipeline.executar`/`construir` → o acumulador. Só o pede quem roda antes do *build*: o passo 7 de `recovery-restore` (`Makefile:803`) e a linha C do ciclo, com o modo explícito, nunca deduzido da ausência de `LIMITE`. Nele, um painel ao vivo, inclusive misto (`ao_vivo` > 0), reprova a execução antes de qualquer travessia, e a falha não vira confirmação | Não | 1 |
| 5 | **A prova quente do GCP** (`gcp/prova_quente.py`): passa ao construtor uma fotografia própria, com o par de teste e o ponto dele, e mantém as travessias de hoje (semente 30, ponto 25, saldo final 23). Não exercita a leitura no BigQuery, que fica declarada como não provada (L9) | Não | 1 |
| 6 | **O acesso do `streamer` ao ponto** (Q76) | Não | 1 |
| 7 | **Os testes.** Saem o teste do espelho (`tests/test_dbt.py:223`) e o uso da variável em `dbt/tests/saldo_da_view_confere_com_o_livro_distinto.sql:104`, que passa a ler o ponto do modelo. Entram: testes unitários do dbt para o modelo, com os casos de borda (par sem venda no ano, par com ponto 2, ruptura, duas versões do produto com venda na janela, troca da versão corrente); a travessia por par e por painel no `tests/test_drenagem.py`; a fotografia (par ausente, relação ausente, relação mudando entre duas instâncias da mesma execução); o acesso no `tests/test_acesso.py`; as contagens de `tests/test_chaves.py:21` (modelos 26 → 27, FKs 58 → 60, colunas medidas depois do desenho) | Não | 1 |
| 8 | **Os documentos do ADR-0057**: glossário (cobertura, ruptura e perguntas de negócio), `metricas.yml`, o `.yml` de `consumption` e de `analytics`, Streaming, Qualidade de Dados e Governança §7; e, pelo modo de carga, Execução Local §3 (linha 10) e §3.2 (passo 4), e Capacidade §3.4, a restauração | Não | 1 e 4 |
| 9 | **O ciclo** (Q77): a prova do *streaming* ao vivo com o limiar por par, o antes → depois das 16 views medido e a base publicada sem os eventos do exercício (D93) | Sim, descartado e refeito | 3 |
| 10 | **A entrega:** Consumidores §5 e §6, os Achados, o pacote, a *tag* (Q78) e os avisos aos três consumidores | Não | 4 |
| 11 | **As amostras de registros** (D95, [ADR-0058](docs/adr/0058-amostras-de-registros-para-o-publico.md) e a retificação dele): `make amostras`, o exportador de `docs/amostras_de_registros.json`, e o esquema JSON dele. **Recusa** procedência que não seja `verified`. **Cobre** o conjunto de relações do pacote da mesma publicação (283 previstas). **Ordena** pela chave declarada, com o *fallback* até todas as colunas; nas relações em que a linha carrega a própria evidência de defeito (`raw_legacy.*`, `stg_legacy__*`, `legacy_classifications`, `legacy_eligible_records`), as defeituosas vêm primeiro, pelo predicado da segunda retificação do ADR-0058; nas pontes, agregados, *snapshots*, dimensões e relações que juntam as origens, só a chave. **Mascara** as colunas `personal` e, nos *payloads*, as folhas `personal` da relação de origem (dependência declarada em `stg_legacy__*`; `source_table` em `trusted.legacy_*` e na quarentena; coleções linha a linha; `findings` pelo `column`); origem ou forma não resolvida vira marcador inteiro; o conteúdo deslocado pelo defeito aparece como está (Owner, 19/11/2026). **A amostra é do *build* que ela cita** (RVPR-4-01): `make amostras-check`, só leitura, refaz a exportação em memória **na mesma invocação** do cabeçalho e compara tudo, sem campo ignorado; com outra invocação, recusa. O `check-offline` valida o esquema, a cobertura igual ao conjunto de relações do pacote e a máscara estrutural. **As provas:** por ocorrência, com o esperado calculado à parte do exportador; a varredura dos valores pessoais fortes, com os curtos fora e a exceção do deslocado listada do manifesto; contraprovas de vazamento deliberado, de coincidência curta legítima, de JSON escapado e do caso `support_agents` linha 2. Os documentos do ADR-0058 | Não | 1 e 4 |

**Fica fora**, com o motivo:
- **A posição de estoque com o pedido em aberto** (`quantity_outstanding`): o ADR-0057 a deixou de fora. A P12
  pergunta quem está abaixo do ponto agora, não quanto pedir.
- **O alerta comparar o disponível em vez do saldo físico:** o caminho quente não transporta reservas
  (ADR-0057, Consequências). Mudar isso é outro fluxo.
- **Mudar o gerador** para a venda ficar menos esparsa: o ADR registrou que, com este dado, "abaixo do ponto"
  coincide com "ruptura", e aceitou o custo. Engrossar a venda seria outra regeneração declarada, com decisão
  própria.

---

## 2. Os blocos, na ordem

### Bloco 0 — a abertura (só documentos)

1. Este plano, revisado por outro agente antes de qualquer código.
2. O README e Consumidores §5 passam a apontar para ele como o plano da fase em curso (RVPR-1-08).
3. Uma linha `prevista` em Consumidores §5 para cada mudança de **esquema** visível ao consumidor: a relação nova
   em `analytics`, que entra no pacote com PK e FKs (Q75), feita em 18/11/2026; e o arquivo das amostras (D95),
   feita em 19/11/2026. Cada uma vira `feita` no fim, sem linha nova. A mudança de
   valor da P12 entra uma vez só, já `feita`, no fim (a regra da seção).

### Bloco 1 — o código e os testes, sem dado

Os itens 1 a 8, nesta ordem: as variáveis e o modelo; a P12; a referência; o *streaming*; a prova quente; o
acesso; os testes; os documentos.

**Onde, e com que portão** (RVPR-1-04, RVPR-2-01, RVPR-2-02). `make test` **não isola** nada: as conexões dos
testes são as do `.env`. E o `check-offline` não pode ficar verde antes do primeiro *build*: ele confere o pacote
contra os insumos e contra a coleta do pytest (`pacote --conferir-pytest`, `test_o_pacote_esta_em_dia_com_os_insumos`),
e o pacote só se refaz com o manifesto de um *build*. Uma *branch* com *commits* nasceria vermelha, como a
reabertura já tinha visto. Por isso o bloco segue o procedimento do Bloco 3 da reabertura:
- o código fica **fora da árvore**, em *patches* por assunto em `data/medicoes/ponto_de_reposicao/bloco1/`, com
  SHA-256;
- antes de congelá-los, eles são aplicados numa **cópia de trabalho temporária**, com a suíte offline (só as
  guardas do carimbo do pacote podem reprovar, e cada uma reprovada é nomeada) e o dbt compilado fora de
  `dbt/target`. O resultado fica ao lado dos *patches*;
- contra o armazém publicado, **só leitura**: `dbt parse`, `dbt compile` e a consulta compilada do modelo numa
  transação `READ ONLY`. **Nenhum `dbt test`**, nem o unitário: o `on-run-end` reaplica as concessões
  (`aplicar_acesso_por_camada`), e o teste unitário cria uma relação temporária (RVPR-2-01).

Os testes unitários do dbt e os que pedem o modelo materializado (o contrato, a PK e as FKs do ADR-0056, as
concessões, a auditoria da P12, as contagens de `test_chaves`, o `dbt/tests` de saldo) rodam **no ciclo**, na
linha D′, sobre o estado que vai ser descartado. Os *commits* nascem ali, sobre o estado validado, como na F0 da
reabertura.

**Os oráculos do bloco:**
- o modelo contra a fórmula escrita à mão, nos casos de borda do item 7;
- a consulta compilada do modelo, só leitura, contra a medida do §3: 3.047 pares, com 1.387 de ponto 0, 1.637 de
  ponto 1 e 23 de ponto 2, e 213 abaixo. A medida foi feita por versão, e hoje cada SKU tem uma versão só, então
  as duas devem coincidir. Se não coincidirem, o bloco para para entender a diferença, **sem ajustar o modelo
  ao número**;
- a travessia por painel no executor local do Beam, sobre o `TestStream` de `test_drenagem.py`: dois pares com
  pontos diferentes e o mesmo delta, um cruzando e o outro não; um par ausente da fotografia; o contrato da D63
  intacto, com todo painel chegando ao publicador, inclusive sem alerta e com ponto zero;
- a contraprova do acesso, que roda no ciclo: o `streamer` lê o ponto e continua sem ler o resto de `analytics`.

### Bloco 2 — a adaptação do ciclo (antes de qualquer passo destrutivo)

A forma da reabertura (Q77), com um diário próprio, `data/medicoes/diario_ponto_de_reposicao.md`. Ela fixa,
antes do primeiro descarte e revisada por outro agente:
- **o estado de partida**, medido: `HEAD`, árvore, cursor do produtor, geração, lote do legado, DAG, memória livre;
- **o corte de recuo**: o pacote de recuperação da `v2.2.0`, verificado contra o banco (`recovery-verify
  CONTRA_O_BANCO=1`), com SHA-256 e cópia fora do *checkout*;
- **os parâmetros**: `LIMITE`, `QUANTAS` e o prazo da D63, os mesmos da reabertura salvo motivo escrito; a época
  do livro de capturas que se encerra e a que abre;
- **as transições do legado desta geração**, medidas antes do descarte. As 26 remoções da Q74 não são
  transportadas como expectativa;
- **os oráculos de cada linha**, inclusive o do alerta, abaixo;
- **os `FORCE`**: os de descarte, confirmados pelo Owner no passo em que rodam. O do *preflight* de memória
  continua proibido sem a máquina liberada pelo Owner (`CLAUDE.md` §5).

O ciclo começa com a revisão da adaptação sem bloqueio e com o Owner presente para os `FORCE`.

### Bloco 3 — o ciclo

Mesma sequência do ciclo da reabertura (`data/medicoes/diario_reabertura.md`, linhas A a G), com uma diferença:
**o gerador não muda**, então a regeneração refaz as mesmas origens da `v2.2.0`. Ela só existe para descartar o
exercício (D93, forma (e)). O oráculo das fontes compara conteúdo e parâmetros, e precisa dar igual à medida de
partida; o `geracao.json` ganha carimbo novo, e isso não conta como diferença.

1. **A — o antes.** A captura das 16 views, numa transação `REPEATABLE READ READ ONLY`, sobre o armazém da
   `v2.2.0`, com SHA-256; as guardas do F31 na fase (i); a T3 sobre o estado de partida.
2. **D′ — o primeiro *build* do código novo**, ainda sobre o estado de partida, para o modelo do ponto existir
   antes do lançamento do *pipeline*. A sequência da F0 da reabertura: os *patches* aplicados, `dbt-build`,
   `catalog`, `test` (com os testes unitários do dbt e os que pedem o modelo), `catalog`, `check-offline` verde,
   e só então os *commits* por assunto, sobre o estado validado. A captura das 16 views: **o depois esperado**,
   em que só a P12 muda.
3. **E — o exercício de *streaming***, como E1 a E10 da reabertura: o produtor, a duplicação, a drenagem da D63,
   o encerramento da V6, a sincronização, o *build* incremental e a comparação dos dois caminhos. **O oráculo
   novo do alerta**, sobre a fotografia guardada na execução e a leitura completa do tópico entre os *offsets*
   H0 e o final (o `stream-alerts` é só observação):
   - **a fonte por painel** é desenhada no Bloco 2: as confirmações da D63 guardam a contagem e a presença de
     alerta, sem o delta, o saldo nem a ordem dos painéis (`drenagem.py`), e o oráculo precisa deles;
   - todo alerta traz no `limiar` o ponto do par na fotografia;
   - recalculando o saldo físico **por painel**, como o acumulador, cada travessia do ponto, para baixo ou para
     cima, tem exatamente um alerta, e nenhum alerta existe sem travessia. Oscilação dentro de um painel não
     conta;
   - pelo menos uma abertura e uma normalização. Zero reprova a linha, porque nada teria sido exercitado. O
     número é medido, não previsto: com pontos de 0 a 2, só pares de ponto 1 ou 2 podem abrir, e aumentar o
     `LIMITE` não garante abertura. Se der zero, a linha para e a saída vai ao Owner.
4. **B — o descarte**: `stream-down FORCE=1`, `stream-reset-sink FORCE=1`, `seed-data FORCE=1` e
   `seed-legacy FORCE=1`, cada um confirmado pelo Owner; o oráculo das fontes contra a medida de partida (40
   `equal`); o cursor do produtor tratado como na B6 da reabertura.
5. **C — a publicação sem produtor**: `sync-airbyte RESET=1`, o *snapshot* do CDC (`medir CENARIO=streaming`,
   sem produtor, no modo da Q79) e a comparação dos dois caminhos.
6. **D — o *build* publicado**: a captura do legado, o `dbt-build RESET=1`, as guardas na fase (iii), a
   procedência `verified`, o `check` e a DAG real.
7. **H — o depois.** A captura das 16 views. Dois oráculos: contra a A, **só a P12 muda**; contra a D′, **as 16
   são idênticas** nas colunas publicadas (as chaves internas do SCD podem mudar com o `RESET`). A diferença da
   P12 publicada por linha (só antes, só depois, as comuns que mudam), com o motivo de cada grupo.
8. **G — a recuperação**: o pacote de recuperação renovado e a restauração com a V7. O passo 7 dela, o
   *snapshot* do caminho quente, roda **antes** do *build* e encontra o modelo ausente ou o do estado substituído
   (RVPR-1-02): roda no modo da Q79. Depois, a T3 na época nova, a promoção (confirmada pelo Owner), as
   retenções conferidas e o estado devolvido.

#### O que a base publicada não prova

Como na reabertura: a entrega de eventos vivos, as transições de alerta, a parcela quente da P12 e o avanço
incremental depois deles ficam provados no exercício, sobre o estado descartado, e não sobre o publicado. A
leitura do ponto pelo lançador do Dataflow no BigQuery não é exercitada (L9).

### Bloco 4 — a entrega

1. **Consumidores §5**: a linha `feita` da P12, com o antes → depois medido na H e o motivo; a `prevista` do
   modelo novo passa a `feita`. **§6**: o marco a preferir passa a ser a *tag* nova, sem citar o próprio
   *commit* (RVPR-1-08).
2. **Achados**: o F36 com o que foi feito.
3. **O pacote** regenerado (`make catalog`), com o carimbo de execução em *commit* próprio.
4. **As amostras** (item 11), em ordem (RVPR-3-03, RVPR-4-01, RVPR-4-02). O exportador, a conferência e os testes
   deles, com *fixtures*, entram nos *commits* da D′. **O arquivo só nasce depois da G**, do estado final restaurado e
   promovido, com a árvore limpa e a procedência `verified`, para nenhum `check` interno da restauração encontrá-lo:
   1. `make amostras` e, na mesma invocação, `make amostras-check` e as provas da máscara;
   2. um *commit* com o arquivo e a validação offline dele no `check-offline`; ele não toca `dbt/`, `src/` nem os
      insumos do pacote, e por isso não pede *build* novo;
   3. a `prevista` do arquivo em Consumidores §5 passa a `feita`.
   Uma restauração futura não reprova por causa do arquivo: ele continua a amostra do *build* que cita, e a
   publicação seguinte o refaz.
5. **A revisão do fechamento** por outro agente; depois o *push* e a *tag* (Q78).
6. **Os avisos**, em `data/medicoes/base_consumidores/avisos/`:
   - `bi-como-codigo` e `nl_sql`: um aviso só cada, da `v2.1.0` à *tag* nova. Ele cita os avisos de 18/11/2026,
     sem reescrevê-los, e junta o que esta fase mudou. O trecho "o F36 está aberto" deixa de valer, e o
     denominador da P12 é 3.047 (o aviso do BI de 18/11 dizia 3.046). O alerta físico e a P12 disponível não são
     apresentados como equivalentes;
   - `gdados`: um aviso curto, pela caixa de correio (`~/Projetos/gdados/alinhamento.md`): a P12, o modelo
     novo no pacote, as amostras (a D06 dele) e o registro do GCP sanitizado, que a *tag* passa a levar.

---

## 3. O que já foi conferido para escrever este plano (sem efeito)

Medidas só de leitura no armazém da `v2.2.0`, em 18/11/2026. As consultas e as saídas estão em
`data/medicoes/ponto_de_reposicao/medida_adr/` (fora do Git):
- **o prazo** (`f36.sql`): do pedido ao primeiro recebimento, mediana de 28,4 dias em 1.116 itens do varejo, com
  p10 de 6,4 e p90 de 53,5; no legado, 17 itens, mediana de 34,8. Por fornecedor do varejo, as medianas vão de
  10,8 a 48,3 dias. **O prometido** (`f36d.sql`, `expected_at − ordered_at` dos pedidos não cancelados): mediana
  de 26 dias em 389 pedidos do varejo, p10 de 11 e p90 de 42;
- **os pares** (`f36d.sql`): 3.047 no livro, contados por versão e por chave natural, todos com versão corrente.
  **Nenhum SKU tem mais de uma versão** em `dim_product`, nem armazém em `dim_warehouse`. A projeção de saldo
  (`trusted.inventory_balances`) tem 3.046: falta o par legado (1, 12), o `NUM_OUT_OF_RANGE` do resíduo zero da
  reabertura (`D5_a1_residuo_zero.json`). A P12 a lê por *left join*, então o universo dela é 3.047. O texto do
  F36, de Consumidores §5 e do ADR dizia 3.046, e foi corrigido;
- **a demanda** (`f36.sql`, `f36b.sql`): 578 pares venderam nos 90 dias, 1.660 em 365 e 2.602 em algum momento dos
  974 dias do histórico. Das 410 rupturas, 213 venderam no ano e 30 nunca venderam;
- **o ponto da regra decidida** (`f36c.sql`): 0 para 1.387 pares, 1 para 1.637 e 2 para 23. Os 213 abaixo do
  ponto estão todos com o disponível em zero ou menos;
- **o código**: o limiar é lido em `streaming/config.py`, usado em `pipeline.py` (`AcumularSaldoEAlertar`,
  `ramo_de_alerta`) e citado em `cli.py`, `producer.py` (comentário), `gcp/prova_quente.py`,
  `tests/test_drenagem.py` e `tests/test_prova_quente.py`; a variável do dbt, em `skus_below_reorder_point.sql`,
  `dbt/tests/saldo_da_view_confere_com_o_livro_distinto.sql`, `tests/test_dbt.py` e
  `tests/test_auditoria_das_views.py`. Nenhum limiar fixo na DAG, na recuperação ou no compositor do pacote
  (revisão, RVPR-1-05). A semente local do saldo consulta o armazém pelo `sink.engine()`, a conexão do `.env`;
- **os snapshots não alertam**: `AcumularSaldoEAlertar.process` constrói o saldo dos painéis do *snapshot* sem
  avaliar travessia (`if not painel["ao_vivo"]`). Por isso o modo da Q79 é seguro para as execuções sem
  produtor;
- **o acesso**: o `on-run-end` revoga do `streamer` tudo em `analytics` e `consumption` a cada execução
  (`aplicar_acesso_por_camada`), e `tests/test_acesso.py` assume cada papel e prova o permitido e o proibido. No
  BigQuery, `dbt/macros/grants_no_bigquery.sql` traduz o `grants` do modelo em `roles/bigquery.dataViewer` na
  relação.

**Não verificado**: nenhum código foi escrito, e nenhum alvo do ciclo rodou. A duração do ciclo não foi
estimada além da reabertura, que levou cerca de seis horas (das 17:56 à meia-noite de 18/11/2026). Não se sabe
quantas aberturas de alerta o exercício dará com pontos de 0 a 2. A geração idêntica das origens se apoia na
B5 da reabertura e nos testes de determinismo (`tests/test_determinismo.py`, `tests/test_legado.py`), não numa
segunda geração desta fase.

---

## 4. Riscos

| Risco | Efeito | O que o plano faz |
|---|---|---|
| A regeneração não refazer as origens iguais | O antes → depois mistura a regra com o dado | O oráculo das fontes contra a medida de partida (B), e a H contra a D′ |
| O exercício dar zero aberturas com pontos de 0 a 2 | A prova do alerta passa sem exercitar nada | Zero reprova a linha E, que para e vai ao Owner |
| O ponto do modelo e o da referência errarem juntos | A auditoria aprova um erro | A referência calcula o ponto pelos parâmetros, sem ler o modelo (item 3) |
| O lançamento ler um ponto velho ou nenhum | O alerta avalia contra o estado errado, ou todos os pontos zero, calado | A relação ausente ou vazia faz o lançamento falhar; só o modo da Q79 dispensa a fotografia, e nele um painel ao vivo faz a execução falhar |
| O `streamer` ganhar mais que o ponto | Quebra o menor privilégio | A contraprova e o `test_acesso`, no ciclo |
| Memória da máquina (R11) | O ciclo troca Airbyte, Airflow e *streaming* | Os alvos fazem a troca; recusa do *preflight* para o ciclo até o Owner liberar a máquina |
| Consumidor fixar a `v2.2.0` durante a fase | Lê a P12 que "responde quase tudo" | O aviso de 18/11 já diz para não ler a P12 como sinal de reposição; o `gdados` foi avisado do F36 |

---

## 5. Decisões pedidas ao Owner — rodada 1

### Q75 — onde mora o ponto de cada par, e como ele se liga ao produto

O ADR-0057 fixou "um modelo dbt no grão do par" e deixou o lugar para o plano. O [ADR-0013](docs/adr/0013-nomenclatura-por-prefixo-de-tipo.md)
nomeia dimensão (`dim_`), fato (`fact_` + grão) e view de consumo (pela pergunta).

| Opção | A favor | Contra |
|---|---|---|
| **(a) `analytics.dim_sku_location`**, dimensão tipo 1 do par, com o ponto e os seus insumos como atributos (recomendada) | É a entidade que o varejo chama de item-local, a que guarda o ponto num ERP. Entra no contrato do ADR-0056 e no pacote como as outras. Se um dia a origem trouxer o ponto, ele substitui o calculado no mesmo lugar | Atributo derivado de fato numa dimensão: o valor muda a cada *build*, sem histórico. O `analytics` passa de 26 para 27 modelos, e as FKs de 58 para 60 |
| (b) `analytics.fact_inventory_position`, uma fato de fotografia no grão do par, no corte do lote | O ponto é uma medida derivada do movimento, e fato é o lugar de medida | "Posição de estoque" é, no livro-texto, o saldo mais o pedido em aberto, que o ADR excluiu: o nome induz ao erro. Uma fato sem data no grão é estranha ao resto de `analytics` |
| (c) Uma view de `consumption` só para o ponto | Fica na camada que o consumidor já lê | O `consumption` é nomeado por pergunta de negócio (ADR-0018), e esta não é uma; o objeto 17 muda a contagem das views em todos os documentos e na auditoria |

**Na (a), a identidade e as chaves** (RVPR-1-01). A fato liga o movimento à versão do produto vigente nele
(ADR-0017), e a `dim_product` é SCD tipo 2. A dimensão nova não herda isso:
- **a identidade** é natural: `(source_system, warehouse_natural_key, product_natural_key)`, como a P12 agrega;
- **a PK**, `sku_location_key`, é o *hash* dessa identidade (`dbt_utils.generate_surrogate_key`, como a
  `dim_warehouse`), estável quando o produto ganha versão nova;
- **a venda** é somada através de **todas** as versões do produto, resolvidas para a chave natural antes de
  agregar;
- **as FKs**, resolvidas **depois** de agregar: `warehouse_key` (a `dim_warehouse` é tipo 1, uma linha por
  armazém) e `product_key` da **versão corrente** (`is_current`). Quando a versão corrente muda, a FK acompanha e a
  PK fica. O par sem versão corrente do produto fica fora, como fica fora da P12, que junta pela corrente; hoje
  são zero;
- as chaves históricas da fato não mudam, e as FKs seguem o mecanismo do ADR-0056.

### Q76 — o acesso do `streamer` ao ponto

| Opção | A favor | Contra |
|---|---|---|
| **(a) `select` do `streamer` só na relação do ponto**, declarado no `grants` do modelo, ao lado do `transformer`. A concessão declara a dependência e é provada assumindo o papel (`SET ROLE streamer`); **a leitura em si é do lançador, com a credencial de quem o lança** (no local, o login do `.env`; na nuvem, a ADC do Owner, porque `--service_account_email` vale só para os *workers*), como hoje todo componente (Governança §7; RVPR-2-03). No BigQuery, a mesma declaração vira `dataViewer` na relação pela macro que já existe (`grants_no_bigquery`), sem Terraform (recomendada; RVPR-1-07) | O menor privilégio que funciona; uma autoridade só para a concessão, o dbt; o `test_acesso` prova o permitido e o proibido; a dependência do alerta fica declarada | Muda a matriz da Governança §7, onde o `streamer` hoje só lê a própria tabela. O `on-run-end` deixa de revogar do `streamer` o `usage` de `analytics` |
| (b) Não declarar nada, porque o lançador se conecta hoje pelo superusuário | Nenhuma mudança de acesso | A dependência fica escondida e quebra no dia em que o *streaming* se conectar como `streamer`, o passo que a Governança §7 já prevê |
| (c) O dbt publicar o ponto em `raw`, onde o `streamer` já está | Nenhum papel novo | Inverte as camadas: um modelo escrevendo na aterrissagem das origens |

### Q77 — a prova do alerta com o limiar por par

| Opção | A favor | Contra |
|---|---|---|
| **(a) O ciclo da reabertura**: o exercício sobre o estado de partida, o descarte por regeneração idêntica e a publicação sem produtor (recomendada) | A prova ao vivo que o ADR-0057 aceitou pagar, numa sequência já executada e revisada; dá de graça o oráculo "H igual a D′" | Cerca de seis horas de ciclo, como na reabertura, com os `FORCE` de descarte e a troca de ambientes |
| (b) O exercício sobre o estado de partida, e o descarte pela restauração do pacote da `v2.2.0` | Não regenera as origens | A restauração é mais lenta que a regeneração (a G7 da reabertura), e a sequência "exercício → restauração" nunca rodou como descarte |
| (c) Só o executor local do Beam, sem o transporte real | Nenhum passo destrutivo | Não prova a leitura do ponto no armazém real nem a entrega; fica contra o P10 e contra o que o ADR aceitou |

### Q78 — a *tag* da fase

| Opção | A favor | Contra |
|---|---|---|
| **(a) `v2.3.0`** (recomendada) | O esquema das 16 views não muda; o pacote ganha uma relação, de forma aditiva; a regra muda e vem com aviso | — |
| (b) `v3.0.0` | Marca a mudança de regra publicada | Sugere quebra de contrato, e nenhuma coluna muda |

A Q78 fica para o fechamento: não muda o desenho.

### Q79 — as execuções de *streaming* que rodam antes do *build* (RVPR-1-02)

O *snapshot* do caminho quente roda antes do `dbt-build` em três lugares: o passo 7 da restauração
(`Makefile:802`), a linha C do ciclo e o ciclo do zero. Nos três, o modelo do ponto não existe (o pacote de
recuperação não leva `analytics`) ou é o do estado que está sendo substituído. Muda o contrato da recuperação,
então é decisão do Owner (`CLAUDE.md` §5).

| Opção | A favor | Contra |
|---|---|---|
| **(a) Um modo explícito de carga, sem fotografia**, pedido pelo chamador (`medir CENARIO=streaming` sem produtor e o passo 7 da restauração). O lançador não lê o ponto e registra o modo na execução; um painel **ao vivo** nesse modo faz a execução falhar, em vez de avaliar contra ponto nenhum (recomendada) | O *snapshot* não alerta por desenho (`painel["ao_vivo"]`), então nada se perde; a ausência do modelo nunca é engolida em silêncio; a ordem da restauração não muda | Um parâmetro novo no lançador e nos dois chamadores, com contraprova |
| (b) Reordenar a restauração e o ciclo para o *build* vir antes do *snapshot* | Um modo só de execução | O *build* precisa do `raw`, que vem da sincronização, e a ordem atual foi provada assim. Mexe numa sequência validada, com risco maior |
| (c) Modelo ausente vira mapa vazio, com todos os pontos zero | Nenhuma mudança nos chamadores | Engole ausência, falta de permissão e falha de leitura: um alerta ao vivo seria avaliado contra zero, calado (RVPR-1-02) |

### Respostas do Owner (18/11/2026)

Nesta sessão, perguntadas com as opções acima, depois da rodada 1 aplicada: **Q75 (a)**, `analytics.dim_sku_location`,
com a identidade e as chaves descritas; **Q76 (a)**, o `select` do `streamer` só nela, pela concessão do dbt;
**Q77 (a)**, o ciclo da reabertura; **Q79 (a)**, o modo de carga explícito. A Q78 fica para o fechamento.

---

## 6. Definição de pronto aplicada

Os itens do `CLAUDE.md` §7, com o que cada um significa aqui:
- migrações aplicáveis do zero: nenhuma migração nova é esperada; se o modelo pedir, ela entra no Bloco 1;
- *pipeline* de ponta a ponta: a linha D do ciclo, com a DAG;
- testes de qualidade e reconciliação: o `check`, a auditoria das views e a comparação dos dois caminhos;
- catálogo, dicionário e linhagem: o `make catalog` no Bloco 4;
- campos novos classificados: as colunas do modelo do ponto, pela derivação da sensibilidade;
- cobertura: os casos de borda do item 7, todos representados nos testes;
- segredos e `.gitignore`: o `check-offline` em cada *commit*;
- revisão: integral no declarativo (as variáveis, o modelo, o `.yml`, o `fluxo.yml`, a concessão, o modo da Q79)
  e por amostragem no derivado;
- documentação sem duplicar: cada assunto no dono do §1, item 8;
- decisões em ADR: o ADR-0057, e as respostas da Q75 a Q79 aqui;
- critérios da fase: P12 com o ponto por par, alerta com o mesmo ponto provado ao vivo, H igual a D′, *tag* e
  avisos.

---

## 7. Rodadas de revisão

### Rodada 1 — codex2, sobre `37d32d1` (18/11/2026)

Parecer em `data/medicoes/ponto_de_reposicao/codex2_plano_r1.md` (fora do Git). Nada bloqueava o Bloco 0; quatro
bloqueantes de desenho impediam o Bloco 1.

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVPR-1-01 | O grão natural do par e a FK para a `dim_product` SCD2 não estavam definidos, e a medida agrupa por versão | bloqueante | **Aceito.** A Q75(a) fixa a identidade natural, a PK por *hash* dela, a venda somada através das versões e as FKs resolvidas depois de agregar, com a versão corrente. Medido (`f36d.sql`): hoje cada SKU tem uma versão só, e as contagens por versão e por chave natural coincidem (3.047). O oráculo do Bloco 1 para e investiga se divergirem, sem ajustar o modelo ao número. Casos de duas versões e de troca da corrente nos testes (item 7) |
| RVPR-1-02 | A leitura obrigatória do ponto cria uma dependência que a restauração e o ambiente vazio não satisfazem | bloqueante | **Aceito.** Conferido: o passo 7 da restauração roda o *snapshot* antes do *build* (`Makefile:802–803`), e o pacote não leva `analytics`. Virou a **Q79**, com o modo de carga explícito recomendado. Relação ausente fora desse modo faz o lançamento falhar (item 4) |
| RVPR-1-03 | Ler a tabela no `setup()` de cada instância não congela o ponto por execução | bloqueante | **Aceito.** O ponto passa a ser lido uma vez, pelo lançador, e levado pelo construtor a todas as instâncias; a fotografia fica guardada na execução. O corte D62 do saldo não muda; o filtro `retail` entra antes de montar o mapa; o oráculo da E confere por painel e pela leitura completa do tópico. O ADR-0057 foi corrigido (ainda não publicado) |
| RVPR-1-04 | `make test` não fornece o banco isolado que o plano afirmava | bloqueante | **Aceito.** Conferido em `tests/conftest.py`. O Bloco 1 passa a só ler o armazém publicado (`parse`, `compile`, testes unitários do dbt, a consulta compilada em `READ ONLY`); o que pede o modelo materializado roda na D′, sobre o estado a descartar; o código fica num ramo até o `check` passar ali |
| RVPR-1-05 | O inventário omitia `dbt/tests/saldo_da_view_confere_com_o_livro_distinto.sql`, o carregador da auditoria e as contagens de `test_chaves` | ajuste | **Aceito.** Os três entram nos itens 3 e 7; o número de colunas fica para depois do desenho |
| RVPR-1-06 | A explicação de 3.047 contra 3.046 não se sustentava, e a mediana do prometido não tinha consulta | ajuste | **Aceito.** Medido (`f36d.sql`): o par a mais é o legado (1, 12), ausente da projeção de saldo; a P12 a lê por *left join*. O denominador foi corrigido no F36, em Consumidores §5 e no ADR (ainda não publicado). O prometido ganhou consulta e saída: mediana de 26 dias em 389 pedidos |
| RVPR-1-07 | A concessão no BigQuery já é do dbt; o Terraform não deriva concessão de modelo | ajuste | **Aceito.** A Q76(a) passa a usar a macro `grants_no_bigquery`, sem Terraform; o ADR-0057 cita a concessão do dbt |
| RVPR-1-08 | Faltava atualizar os ponteiros permanentes de Consumidores para a fase e o marco novos | ajuste | **Aceito.** O ponteiro do §5 já aponta este plano; o §6 entra no Bloco 4 |

**Fora do escopo do F36, visto pelo revisor:** um aviso novo do `gdados` na caixa de correio (a D06 dele, a
proposta de amostras de linhas para o portal). É outro assunto, atendido à parte.

### Rodada 2 — codex2, sobre `c1c8f95` (19/11/2026)

Parecer em `data/medicoes/ponto_de_reposicao/codex2_plano_r2.md` (fora do Git). O desenho central passou; dois
bloqueantes no portão do Bloco 1.

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVPR-2-01 | O teste unitário do dbt não é só leitura: cria relação temporária e o `on-run-end` reaplica concessões | bloqueante | **Aceito.** Os testes unitários saem do Bloco 1 e vão para a D′. Contra o armazém publicado, só `parse`, `compile` e a consulta compilada em `READ ONLY` |
| RVPR-2-02 | O `check-offline` verde por *commit* é inexequível antes do *build*, por causa do carimbo do pacote | bloqueante | **Aceito.** O Bloco 1 passa ao procedimento do Bloco 3 da reabertura: *patches* fora da árvore, validados numa cópia temporária com as guardas do carimbo nomeadas, e os *commits* na D′, sobre o estado validado (sequência da F0) |
| RVPR-2-03 | A concessão ao `mvp-streamer` não é a identidade do lançador que lê a fotografia | ajuste | **Aceito.** A Q76(a) e a retificação do ADR-0057 dizem quem lê (o login do `.env`; a ADC do Owner na nuvem) e o que a concessão prova; ler como `streamer` fica para o passo geral da Governança §7 |
| RVPR-2-04 | Faltava a cadeia completa do modo de carga e os procedimentos permanentes | ajuste | **Aceito.** O item 4 traz a cadeia até o acumulador e os dois chamadores, com o modo explícito e a reprovação do painel misto; o item 8 inclui Execução Local §3 e §3.2 e Capacidade §3.4 |
| RVPR-2-05 | O ADR aceito foi reescrito no lugar | ajuste | **Aceito.** O ADR-0057 voltou ao texto aceito (`66b8415`) e ganhou a retificação de 19/11/2026, na forma do ADR-0056 |
| RVPR-2-06 | O ADR mandava abrir `prevista` da P12 | ajuste | **Aceito.** Corrigido na retificação: a P12 entra uma vez, como `feita`; a `prevista` é da `dim_sku_location` |

**Depois da rodada 2:** o Owner aceitou a proposta das amostras do `gdados` (D95, ADR-0058) e a incluiu nesta fase
(item 11). A rodada 3 a revisa junto.

### Rodada 3 — codex2, sobre `1805ef2` (19/11/2026)

Parecer em `data/medicoes/ponto_de_reposicao/codex2_plano_r3.md` (fora do Git). As respostas da rodada 2 fecham
os achados, e o portão só leitura do Bloco 1 não tem bloqueio residual (o `dbt compile` não roda os *hooks*). Dois
bloqueantes nas amostras (item 11).

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVPR-3-01 | A máscara pela classificação não alcança o conteúdo pessoal deslocado pelo legado (`support_agents`, linha 2, `agent_code = "AGT-0002;Renan;Costela"`), e faltava o contrato dos *payloads* | bloqueante | **Aceito, com decisão do Owner.** Perguntado, ele decidiu não mascarar o deslocado e mostrar o defeito, com as linhas defeituosas primeiro. Medido no manifesto: três `TEXT_DELIMITER`, um só com dado pessoal (um nome sintético), nenhum telefone. O contrato dos *payloads* (origem, coleções, `findings`, não resolvido vira marcador) está no item 11 e na retificação do ADR-0058 |
| RVPR-3-02 | O oráculo "nenhum valor pessoal em lugar nenhum" não era executável | bloqueante | **Aceito.** A prova passa a ser por ocorrência, com o esperado calculado à parte; a varredura complementar só dos valores fortes, com os curtos fora e a exceção listada; contraprovas nos dois sentidos |
| RVPR-3-03 | A guarda das amostras não cabia no ciclo: o `check` troca a invocação antes de conferir | ajuste | **Aceito.** A conferência ignora os campos de execução e exige ancestralidade sem mudança de código; a ordem da primeira publicação e da restauração está no Bloco 4, item 4 |
| RVPR-3-04 | 282 é a medida de partida; a entrega terá 283 | ajuste | **Aceito.** A cobertura é o conjunto do pacote da mesma publicação, com igualdade exigida; retificação do ADR-0058 e a `prevista` de Consumidores ajustadas |
| RVPR-3-05 | O ADR-0058 ainda atribuía máscara às *policy tags* | ajuste | **Aceito.** Corrigido na retificação; a resposta ao `gdados` remete a ela |
| RVPR-3-06 | O nome não tem garantia de não coincidir | ajuste | **Aceito.** Corrigido na retificação; a máscara já o cobria |

### Rodada 4 — codex2, sobre `98a0910` (19/11/2026)

Parecer em `data/medicoes/ponto_de_reposicao/codex2_plano_r4.md` (fora do Git). A decisão do Owner sobre o legado
está registrada fielmente, e a exposição medida se sustenta: o revisor percorreu os 108 achados e os 25 códigos do
manifesto, e só o `support_agents` linha 2 leva dado pessoal para coluna não pessoal. O portão do Bloco 1 continua
sem bloqueio fora do item 11.

| # | Achado | Veredito | Situação |
|---|---|---|---|
| RVPR-4-01 | A conferência por reexportação não sobrevive ao `check`: o *build* muda o log e a procedência, que estão na amostra | bloqueante | **Aceito.** A amostra passa a ser do *build* que cita: conferida integralmente na mesma invocação, logo depois da exportação; o `check-offline` valida esquema, cobertura e máscara estrutural. Segunda retificação do ADR-0058 |
| RVPR-4-02 | O `check` interno da restauração encontraria a amostra desatualizada, e a ordem da primeira publicação era ambígua | bloqueante | **Aceito.** O arquivo só nasce depois da G, do estado final (Bloco 4, item 4), e não é conferido contra o armazém fora da invocação dele |
| RVPR-4-03 | A prioridade do defeito não estava resolvida por família de relação | ajuste | **Aceito.** O predicado por família está na segunda retificação: prioridade só onde a linha carrega a própria evidência; nas pontes, agregados, *snapshots*, dimensões e mistas, só a chave |
| RVPR-4-04 | A regra de ancestralidade não definia os caminhos | ajuste | **Aceito, por remoção.** Com a amostra presa a uma invocação, a regra deixa de ser necessária e sai |
