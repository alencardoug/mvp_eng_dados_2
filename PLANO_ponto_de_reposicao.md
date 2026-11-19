# Plano — o ponto de reposição derivado da demanda (F36)

| Campo | Valor |
|---|---|
| Estado | **Proposto** em 18/11/2026. Nada foi executado além das medidas de leitura do §3 |
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
| 1 | **O modelo do ponto.** Um modelo dbt no grão do par (origem × armazém × SKU) com a venda de 365 dias, a demanda diária, o prazo, a margem e o ponto, ancorado no último movimento da fato (a forma e o lugar: Q75). As variáveis `reorder_lead_time_days: 28`, `reorder_safety_days: 14` e `reorder_demand_window_days: 365` no `dbt_project.yml`, com a origem da medida no comentário. Sai a `reorder_point_units` | O valor da P12 | 1 |
| 2 | **A P12 lê o ponto do modelo.** `reorder_point` passa a ser o do par, e o filtro `quantity_available < reorder_point`. O resto da view não muda, e **o esquema dela também não**: as mesmas colunas, com os mesmos tipos | O valor | 1 |
| 3 | **A referência independente da P12** (`tests/auditoria/skus_below_reorder_point.sql`) calcula o ponto sozinha, pelos três parâmetros, sem ler o modelo. É o que impede o modelo e a view de errarem juntos | Não | 1 |
| 4 | **O alerta do *streaming*.** Sai o `alerta.limiar_de_unidades` do `fluxo.yml`. O `AcumularSaldoEAlertar` lê, no `setup`, o ponto de cada par do armazém, pelo mesmo caminho da semente do saldo: localmente a consulta ao armazém, na nuvem o `nuvem.Semear`. O par ausente do modelo tem ponto zero. O alerta publica o ponto do par no campo `limiar`. O `cli.py` (`stream-alerts`) e a `prova_quente.py` deixam de supor o 25 | Não | 1 |
| 5 | **O acesso do `streamer` ao ponto** (Q76). Hoje o papel lê e escreve só `raw.inventory_movements_stream`, e o `on-run-end` revoga o resto a cada execução (Governança §7) | Não | 1 |
| 6 | **Os testes.** Sai o teste do espelho (`tests/test_dbt.py`, que conferia `reorder_point_units` contra o `fluxo.yml`), e entram: o modelo contra a fórmula (casos de borda: par sem venda no ano, par só do fluxo, venda que gera ponto 2, ruptura); a travessia com limiar por par no `tests/test_drenagem.py`; a semente do ponto, com o par ausente; o acesso declarado no `tests/test_acesso.py`; e a referência independente na auditoria das views | Não | 1 |
| 7 | **Os documentos do ADR-0057**: glossário (cobertura, ruptura e perguntas de negócio), `metricas.yml`, o `.yml` de `consumption`, Streaming, Qualidade de Dados e, se a Q76 mudar a matriz, Governança §7 | Não | 1 e 4 |
| 8 | **O ciclo** (Q77): a prova do *streaming* ao vivo com o limiar por par, o antes → depois das 16 views medido e a base publicada sem os eventos do exercício (D93) | Sim, descartado e refeito | 3 |
| 9 | **A entrega:** Consumidores §5, os Achados, o pacote, a *tag* (Q78) e os avisos aos três consumidores | Não | 4 |

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
2. O README passa a apontar para ele no estado do projeto.
3. Uma linha `prevista` em Consumidores §5 só se a Q75 trouxer mudança de **esquema** visível ao consumidor: a
   relação nova em `analytics`, que entra no pacote com PK e FKs. A mudança de valor da P12 entra uma vez só, já
   `feita`, no fim (a regra da seção).

### Bloco 1 — o código e os testes, sem dado

Os itens 1 a 7, nesta ordem: as variáveis e o modelo; a P12; a referência independente; o *streaming*; o
acesso; os testes; os documentos. **Commits por assunto**, cada um com `make check-offline` verde, sem *build*
no armazém publicado: o primeiro *build* do código novo é a linha D do ciclo, sobre o estado que vai ser
descartado. Os testes que precisam de banco rodam no banco isolado dos testes (`make test`), nunca no
`source_db`.

**Os oráculos do bloco:**
- o modelo contra a fórmula escrita à mão, linha a linha, nos casos de borda do item 6;
- a medida de leitura do §3 reproduzida pelo modelo compilado, rodada só leitura contra o armazém publicado:
  1.387 pares com ponto 0, 1.637 com 1 e 23 com 2, e 213 abaixo. Se não bater, o bloco para;
- a travessia com limiar por par no executor local do Beam, sobre o `TestStream` de `test_drenagem.py`: dois
  pares com pontos diferentes, um cruzando e outro não com o mesmo delta;
- a contraprova do acesso: o `streamer` lê o ponto e continua sem ler o resto de `analytics`.

### Bloco 2 — a adaptação do ciclo (antes de qualquer passo destrutivo)

A forma da reabertura (Q77), com um diário próprio, `data/medicoes/diario_ponto_de_reposicao.md`. Ela fixa,
antes do primeiro descarte e revisada por outro agente:
- **o estado de partida**, medido: `HEAD`, árvore, cursor do produtor, geração, lote do legado, DAG, memória livre;
- **o corte de recuo**: o pacote de recuperação da `v2.2.0`, verificado contra o banco (`recovery-verify
  CONTRA_O_BANCO=1`), com SHA-256 e cópia fora do *checkout*;
- **os parâmetros**: `LIMITE`, `QUANTAS` e o prazo da D63, os mesmos da reabertura salvo motivo escrito; a época
  do livro de capturas que se encerra e a que abre;
- **os oráculos de cada linha**, inclusive o do alerta, abaixo;
- **os `FORCE`**: os de descarte, confirmados pelo Owner no passo em que rodam. O do *preflight* de memória
  continua proibido sem a máquina liberada pelo Owner (`CLAUDE.md` §5).

O ciclo começa com a revisão da adaptação sem bloqueio e com o Owner presente para os `FORCE`.

### Bloco 3 — o ciclo

Mesma sequência do ciclo da reabertura (`data/medicoes/diario_reabertura.md`, linhas A a G), com uma diferença:
**o gerador não muda**, então a regeneração refaz as mesmas origens da `v2.2.0`. Ela só existe para descartar o
exercício (D93, forma (e)), e o oráculo das fontes precisa dar **igual** à medida de partida.

1. **A — o antes.** A captura das 16 views, numa transação `REPEATABLE READ READ ONLY`, sobre o armazém da
   `v2.2.0`, com SHA-256; as guardas do F31 na fase (i); a T3 sobre o estado de partida.
2. **D′ — o primeiro *build* do código novo**, ainda sobre o estado de partida, para o modelo do ponto existir
   antes do *pipeline*. Captura das 16 views (**o depois esperado**: só a P12 muda).
3. **E — o exercício de *streaming***, como E1 a E10 da reabertura: o produtor, a duplicação, a drenagem da D63,
   o encerramento da V6, a sincronização, o *build* incremental e a comparação dos dois caminhos. **O oráculo
   novo do alerta**: para cada alerta entre os *offsets* H0 e o final, o `limiar` publicado é o ponto do par no
   modelo no instante da subida, e a abertura acontece exatamente quando o saldo físico cruza esse ponto para
   baixo. O número de aberturas é medido, não previsto. Com pontos de 0 a 2, ele deve cair muito em relação às
   77 da reabertura. Zero aberturas reprova a prova, porque nada teria sido exercitado.
4. **B — o descarte**: `stream-down FORCE=1`, `stream-reset-sink FORCE=1`, `seed-data FORCE=1` e
   `seed-legacy FORCE=1`, cada um confirmado pelo Owner; o oráculo das fontes contra a medida de partida (40
   `equal`); o cursor do produtor tratado como na B6 da reabertura.
5. **C — a publicação sem produtor**: `sync-airbyte RESET=1`, o *snapshot* do CDC (`medir CENARIO=streaming`,
   sem produtor) e a comparação dos dois caminhos.
6. **D — o *build* publicado**: a captura do legado, o `dbt-build RESET=1`, as guardas na fase (iii), a
   procedência `verified`, o `check` e a DAG real.
7. **H — o depois.** A captura das 16 views. Dois oráculos: contra a A, **só a P12 muda**; contra a D′, **as 16
   são idênticas**, porque as origens são as mesmas. A diferença da P12 publicada por linha (só antes, só
   depois, as comuns que mudam), com o motivo de cada grupo.
8. **G — a recuperação**: o pacote de recuperação renovado, a restauração com a V7, a T3 na época nova, a
   promoção (confirmada pelo Owner), as retenções conferidas e o estado devolvido.

#### O que a base publicada não prova

Como na reabertura: a entrega de eventos vivos, as transições de alerta, a parcela quente da P12 e o avanço
incremental depois deles ficam provados no exercício, sobre o estado descartado, e não sobre o publicado. A
leitura do ponto pelo Dataflow e pelo BigQuery não é exercitada (L9).

### Bloco 4 — a entrega

1. **Consumidores §5**: a linha `feita` da P12, com o antes → depois medido na H e o motivo. Também a do
   modelo novo, se a Q75 o puser no pacote.
2. **Achados**: o F36 com o que foi feito.
3. **O pacote** regenerado (`make catalog`), com o carimbo de execução em *commit* próprio.
4. **A revisão do fechamento** por outro agente; depois o *push* e a *tag* (Q78).
5. **Os avisos**, em `data/medicoes/base_consumidores/avisos/`:
   - `bi-como-codigo` e `nl_sql`: um aviso só cada, da `v2.1.0` à *tag* nova. Ele junta o que os avisos de
     18/11/2026 já diziam (eles não são reescritos: o novo os cita) e o que esta fase mudou. O trecho "o F36
     está aberto" deixa de valer;
   - `gdados`: um aviso curto, pela caixa de correio (`~/Projetos/gdados/alinhamento.md`): a P12, o modelo
     novo no pacote e o registro do GCP sanitizado, que a *tag* passa a levar.

---

## 3. O que já foi conferido para escrever este plano (sem efeito)

Medidas só de leitura no armazém da `v2.2.0`, em 18/11/2026. As consultas e as saídas estão em
`data/medicoes/ponto_de_reposicao/medida_adr/` (fora do Git):
- **o prazo** (`f36.sql`): do pedido ao primeiro recebimento, mediana de 28,4 dias em 1.116 itens do varejo, com
  p10 de 6,4 e p90 de 53,5; no legado, 17 itens, mediana de 34,8. Por fornecedor do varejo, as medianas vão de
  10,8 a 48,3 dias. O prometido tem mediana de 26;
- **a demanda** (`f36.sql`, `f36b.sql`): dos ~3.047 pares, 578 venderam nos 90 dias, 1.660 em 365 e 2.602 em
  algum momento dos 974 dias do histórico. Das 410 rupturas, 213 venderam no ano e 30 nunca venderam;
- **o ponto da regra decidida** (`f36c.sql`): 0 para 1.387 pares, 1 para 1.637 e 2 para 23. Os 213 abaixo do
  ponto estão todos com o disponível em zero ou menos;
- a contagem da consulta tem **um par a mais que a P12** (3.047 contra 3.046). Ela junta a fato com a
  `dim_product` pela chave da versão, e a P12, pela versão corrente. A diferença não foi investigada; o Bloco 1
  reproduz a medida pelo modelo, que é o que vale;
- **o código**: o limiar é lido em `streaming/config.py`, usado em `pipeline.py` (`AcumularSaldoEAlertar`,
  `ramo_de_alerta`) e citado em `cli.py`, `producer.py` (comentário), `gcp/prova_quente.py`,
  `tests/test_drenagem.py`, `tests/test_prova_quente.py` e `tests/test_dbt.py`. A semente local do saldo
  consulta o armazém pelo `sink.engine()`, a conexão do `.env`, e não pelo papel `streamer` (Governança §7: "hoje
  todos usam o superusuário");
- **o acesso**: o `on-run-end` revoga do `streamer` tudo em `analytics` e `consumption` a cada execução
  (`aplicar_acesso_por_camada`), e `tests/test_acesso.py` assume cada papel e prova o permitido e o proibido.

**Não verificado**: nenhum código foi escrito, e nenhum alvo do ciclo rodou. A duração do ciclo não foi
estimada além da reabertura, que levou cerca de seis horas (das 17:56 à meia-noite de 18/11/2026). Não se sabe quantas aberturas de alerta o exercício dará com
pontos de 0 a 2.

---

## 4. Riscos

| Risco | Efeito | O que o plano faz |
|---|---|---|
| A regeneração não refazer as origens iguais | O antes → depois mistura a regra com o dado | O oráculo das fontes contra a medida de partida (B), e a H contra a D′ |
| O exercício dar zero aberturas com pontos de 0 a 2 | A prova do alerta passa sem exercitar nada | Zero aberturas reprova a linha E. Aumentar o `LIMITE` é a primeira saída, registrada no diário |
| O ponto do modelo e o da referência errarem juntos | A auditoria aprova um erro | A referência calcula o ponto pelos parâmetros, sem ler o modelo (item 3) |
| O `streamer` ganhar mais que o ponto | Quebra o menor privilégio | A contraprova do Bloco 1 e o `test_acesso` |
| Memória da máquina (R11) | O ciclo troca Airbyte, Airflow e *streaming* | Os alvos fazem a troca; recusa do *preflight* para o ciclo até o Owner liberar a máquina |
| Consumidor fixar a `v2.2.0` durante a fase | Lê a P12 que "responde quase tudo" | O aviso de 18/11 já diz para não ler a P12 como sinal de reposição; o `gdados` foi avisado do F36 |

---

## 5. Decisões pedidas ao Owner — rodada 1

### Q75 — onde mora o ponto de cada par

O ADR-0057 fixou "um modelo dbt no grão do par" e deixou o lugar para o plano. O [ADR-0013](docs/adr/0013-nomenclatura-por-prefixo-de-tipo.md)
nomeia dimensão (`dim_`), fato (`fact_` + grão) e view de consumo (pela pergunta). Nenhum desses tipos é
exatamente "o par e a sua política de reposição".

| Opção | A favor | Contra |
|---|---|---|
| **(a) `analytics.dim_sku_location`**, dimensão do par SKU × armazém, tipo 1, com o ponto e os seus insumos como atributos (recomendada) | É a entidade que o varejo chama de item-local, a que guarda o ponto num ERP. Entra no contrato do ADR-0056 (PK por *hash*, FKs para `dim_warehouse` e `dim_product`) e no pacote como as outras. Se um dia a origem trouxer o ponto, ele substitui o calculado no mesmo lugar | Atributo derivado de fato numa dimensão: o valor muda a cada *build*, sem histórico. O `analytics` passa de 26 para 27 modelos, e as FKs de 58 para 60 |
| (b) `analytics.fact_inventory_position`, uma fato de fotografia no grão do par, no corte do lote | O ponto é uma medida derivada do movimento, e fato é o lugar de medida | "Posição de estoque" é, no livro-texto, o saldo mais o pedido em aberto, que o ADR excluiu: o nome induz ao erro. Uma fato sem data no grão é estranha ao resto de `analytics` |
| (c) Uma view de `consumption` só para o ponto | Fica na camada que o consumidor já lê | O `consumption` é nomeado por pergunta de negócio (ADR-0018), e esta não é uma; o objeto 17 muda a contagem das views em todos os documentos e na auditoria |

### Q76 — o acesso do `streamer` ao ponto

| Opção | A favor | Contra |
|---|---|---|
| **(a) `select` do `streamer` só na relação do ponto**, declarado no `.yml` do modelo; na fase GCP, o papel no nível da tabela para `mvp-streamer`, declarado no Terraform e não aplicado (recomendada) | O menor privilégio que funciona; o `test_acesso` prova o permitido e o proibido; a dependência do alerta fica declarada | Muda a matriz da Governança §7, onde o `streamer` hoje só lê a própria tabela |
| (b) Não declarar nada, porque o Beam se conecta hoje pelo superusuário | Nenhuma mudança de acesso | A dependência fica escondida e quebra no dia em que o Beam se conectar como `streamer`, o passo que a Governança §7 já prevê |
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

---

## 6. Definição de pronto aplicada

Os itens do `CLAUDE.md` §7, com o que cada um significa aqui:
- migrações aplicáveis do zero: nenhuma migração nova é esperada; se o modelo pedir, ela entra no Bloco 1;
- *pipeline* de ponta a ponta: a linha D do ciclo, com a DAG;
- testes de qualidade e reconciliação: o `check`, a auditoria das views e a comparação dos dois caminhos;
- catálogo, dicionário e linhagem: o `make catalog` no Bloco 4;
- campos novos classificados: as colunas do modelo do ponto, pela derivação da sensibilidade;
- cobertura: os casos de borda do item 6, todos representados nos testes;
- segredos e `.gitignore`: o `check-offline` em cada *commit*;
- revisão: integral no declarativo (as variáveis, o modelo, o `.yml`, o `fluxo.yml`, a concessão) e por
  amostragem no derivado;
- documentação sem duplicar: cada assunto no dono do §1, item 7;
- decisões em ADR: o ADR-0057, e as respostas da Q75 a Q78 aqui;
- critérios da fase: P12 com o ponto por par, alerta com o mesmo ponto provado ao vivo, H igual a D′, *tag* e
  avisos.

---

## 7. Rodadas de revisão

(vazio)
