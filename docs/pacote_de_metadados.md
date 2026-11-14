# Pacote de Metadados

> **O que vive aqui:** o contrato do pacote da D91, o arquivo que os portais de governança leem
> deste repositório. Cobre o formato, o significado de cada campo, as regras que o consumidor pode
> presumir e o que a versão 1 ainda não leva.
>
> **O que não vive aqui:** por que o pacote existe e por que é assim (ver
> [D91](pendencias.md#d91--o-pacote-de-metadados-para-o-portal-gdados-decidida-em-10112026)); quem
> o consome e por qual canal (ver [Consumidores](consumidores.md)); o conteúdo de cada objeto, que
> é o das declarações (ver [Dicionário de Dados](dicionario_de_dados.md)).

| Campo | Informação |
|---|---|
| Formato | **1** |
| Estado | **Gerado** desde 14/11/2026 (Bloco 4 do [plano da base dos consumidores](../PLANO_base_dos_consumidores.md)), por `make catalog` (`src/mvp_ed1/models/pacote.py`). A especificação veio antes da geração (Q13) |
| Consumidores | `gdados` (E1) e `bi-como-codigo` (etapa 2.7): dois portais, um pacote (Q12, 14/11/2026) |
| Esquema | [`pacote_de_metadados.schema.json`](pacote_de_metadados.schema.json), JSON Schema 2020-12 |
| Exemplo | [`pacote_de_metadados.exemplo.json`](pacote_de_metadados.exemplo.json), validado pelo esquema no `check-offline` |
| Campos acrescentados | 14/11/2026, a pedido do `bi-como-codigo` (UQ-12 a UQ-15): `relations.*.grain`, `relations.*.grants_select`, `checks` e `open_items`. Campo novo, sem mudar o número (§2, regra 3) |

---

## 1. Os arquivos

| Arquivo | O que é | Desde |
|---|---|---|
| `docs/pacote_de_metadados.json` | O pacote. Gerado pelo `make catalog` e versionado; `tests/test_pacote_gerado.py` o confere no `check-offline` | 14/11/2026 |
| `docs/pacote_de_metadados.schema.json` | O esquema do formato. O pacote se valida contra o esquema **do mesmo commit** | 14/11/2026 |
| `docs/pacote_de_metadados.exemplo.json` | Um recorte ilustrativo, com valores copiados do *manifest* local de 13/11/2026 (`generated_at` 22:21:52Z, *invocation* `8eeff407…`). Não é regenerado e não substitui o pacote: os valores dele envelhecem com as correções dos Blocos 1 a 3. O `inputs_sha256` dele é um marcador (64 zeros) | 14/11/2026 |

---

## 2. O que o consumidor pode presumir

1. **Determinismo.** Mesmos insumos, mesmos bytes: UTF-8, chaves em ordem, listas em ordem,
   indentação de dois espaços e quebra de linha no fim. Nenhum carimbo de hora do próprio pacote:
   as datas são as dos artefatos de que ele nasce.
2. **Chave sempre presente.** Toda chave que o esquema declara aparece. A ausência de valor é
   `null`, nunca a string vazia, que o esquema recusa; a lista vazia é `[]`. O portal mostra `null` como **ausente**, nunca como zero ou texto
   vazio. A exceção são os objetos `meta`, repassados do dbt como estão: as chaves deles são as que a
   declaração tem.
3. **Versão.** `format` é um inteiro. Campo novo não muda o número, e o consumidor ignora a chave
   que não conhece. Remover ou renomear um campo, ou mudar o significado dele, muda o número, e o
   aviso sai em [Consumidores §5](consumidores.md#5-o-que-mudou-para-quem-consome).
4. **Nada parcial.** Se falta o *manifest* ou o `run_results.json`, a geração falha e nenhum pacote é
   escrito. Não existe pacote "meio gerado". O mesmo vale para o que os leitores não reconhecem: uma
   pergunta, medida ou pendência fora da forma, ou um caso do JUnit cujo módulo não existe ou que se
   repete, falha a geração em vez de sair do pacote em silêncio.
5. **Texto como dado.** As descrições são Markdown em português, como estão no dbt. O consumidor as
   exibe como texto ou como Markdown saneado, sem executar HTML. Links relativos resolvem contra
   `provenance.link_base` (`docs/`), no commit fixado.
6. **Instantes.** Todo instante é ISO 8601, com o fuso (UTC nos artefatos do dbt). O esquema confere a
   forma; o calendário (o dia que o mês não tem) o gerador confere com `datetime.fromisoformat`, e o
   consumidor que validar só pelo esquema não o alcança.
7. **Nada sensível.** Ficam de fora o SQL compilado, as mensagens de falha dos testes, os dados de
   conexão e os caminhos fora do repositório. O gerador recusa o pacote em que qualquer chave ou valor
   traga caminho de máquina (`/home/…`, `/opt/…`, `C:\…`) — inclusive o identificador de um teste
   parametrizado, que por isso declara `ids` próprios. A sensibilidade de cada coluna está no pacote, e o
   **dado** de nenhuma delas está.
8. **Identificadores.** Relação: `schema.nome`, como no `lineage --json`. Coluna:
   `schema.relação.coluna`. Pergunta: `P01` a `P16`. Teste: o `unique_id` do dbt.

---

## 3. Os campos

| Chave | O que traz | De onde vem |
|---|---|---|
| `format` | `1` | — |
| `provenance.inputs` e `provenance.inputs_sha256` | A lista dos arquivos rastreados pelo Git que alimentam o pacote e o SHA-256 do conteúdo deles, em ordem. Do módulo de teste, o conteúdo é a primeira linha da *docstring*, o único trecho que o pacote lê dele (o `summary` de `checks`) | Os arquivos, no momento da geração |
| `provenance.tree_dirty_at_generation` | Se algum arquivo rastreado diferia do `HEAD` quando o pacote foi gerado. No fluxo normal (mudar a declaração, `make catalog`, *commit*) é `true`, e por isso não prova nada sozinho: quem prova que o pacote versionado bate com os insumos versionados é o `inputs_sha256`, conferido no *commit* fixado. É a "árvore limpa ou suja" da D91, sem citar o próprio *commit* | `git`, no momento da geração |
| `provenance.environment.dbt_target` | O *target* do *profile* do dbt com que os artefatos foram produzidos (hoje só `local`). É o "ambiente" da D91 | O *profile* lido pelo gerador |
| `provenance.dbt` | Versão do dbt, adaptador, `generated_at` e `invocation_id` do *manifest* e do `run_results.json`, todos preenchidos (regra 4) | `dbt/target/` |
| `provenance.warehouse` | Que execução construiu o armazém. Na versão 1, **sempre** `not_verified` e `null`, e o esquema só aceita isso (L5). O estado `verified` entra com o desenho do Bloco 4, como mudança do esquema | Desenho do Bloco 4 |
| `provenance.link_base` | Contra onde resolvem os links relativos dos textos | — |
| `relations` | Cada *source*, *seed*, modelo e *snapshot*: tipo, materialização, descrição, `meta` (domínio, dono, escritores, retenção…) e as colunas, com descrição, tipo declarado, sensibilidade e `meta` | *Manifest* |
| `relations.*.grain` | O grão declarado: o texto entre `**Grão:` e `**` no início da descrição da relação, a convenção das fatos e das dimensões. `null` quando a relação não o declara | Descrição do *manifest* |
| `relations.*.grants_select` | Os papéis que podem ler a relação, em ordem; lista vazia sem concessão. É a matriz de acesso por relação (papéis × camadas sai daí) | `config.grants.select` do modelo, *snapshot* ou *seed*; `meta.grants.select` na *source*, que é o que a macro `aplicar_acesso_por_camada` concede |
| `lineage` | A saída do `python -m mvp_ed1.models.lineage --json`, formato 1, **sem alteração**: por coluna, as folhas imediatas e as origens terminais, com o tipo (`source`, `seed`, `generated`) | `models/lineage.py` |
| `crossings` | As travessias que o dbt não vê (Airbyte, Debezium → Redpanda → Beam, captura do legado), com mecanismo e frequência, em Markdown | `lineage.crossings()` |
| `questions` | As 16 perguntas: título, fatos, medidas com a aditividade (`additive`, `semi_additive`, `non_additive`) e a nota, dimensões e view | [Perguntas de Negócio](glossario_de_negocio/perguntas_de_negocio.md) |
| `description_gaps` | Cada relação ou coluna **declarada** sem descrição, explícita (`column: null` = falta a da relação). O universo é o declarado no *manifest* (modelos, *seeds*, *snapshots* e *sources*). Em 13/11/2026 eram 141 colunas, a G06 | *Manifest* |
| `tests` | Cada teste de dados e teste de unidade do dbt: o que testa, o objeto e a coluna que guarda, onde está declarado e o resultado. `result: null` = **sem resultado**. O resultado traz o estado, a hora, a execução e se ela é a mesma do *manifest* (`same_invocation_as_manifest`) | *Manifest* e `run_results.json` |
| `checks` | Cada teste do `pytest` (`módulo::teste`): o módulo, o que ele guarda (a primeira linha da *docstring* do módulo), a camada (`null` = não declarada: nenhum teste a declara hoje, e o pacote não a infere) e o resultado — estado, hora e execução, ou `null` = **sem resultado**. É onde estão a prova de acesso por execução, as invariantes, as reconciliações e a certificação da captura | O relatório JUnit do `pytest` do último `make test`, o que o `make check` roda (`data/pytest/junit.xml`, fora do Git). Só entra o JUnit da suíte **inteira** de agora, conferido contra a coleta do `pytest` (sem o `PYTEST_ADDOPTS` do ambiente); o parcial ou o de outra coleção sai como `{}`, sem resultado |
| `open_items` | As decisões e verificações em aberto que o portal não pode mostrar como resolvidas: identificador (`Dnn`, `Vn`), título, estado (`pending`, `deferred`), a âncora do texto e os objetos que tocam. `objects: null` = **não declarado** — hoje, todos —, e o portal não infere | [Registro de Decisões](adr/README.md) §3 e [Pendências](pendencias.md) §1 |
| `view_audits` | Para cada uma das 16 views: o estado da auditoria do Bloco 1b (`not_audited`, `audited`, `audit_pending_decision`), o *commit* em que foi auditada, os critérios, o teste de referência e os achados | Declaração versionada do Bloco 1b. Até lá, todas `not_audited` |
| `environments` | A fonte da página de estrutura e ambientes, artefato por artefato: repositório, caminho, se é lido por *commit* ou não está disponível, e a data em que congelou (L4, L10) | Lista declarada no gerador |

**O universo das faltas.** A catraca do `make check` (`tests/test_descricao.py`) percorre as colunas
**materializadas** no armazém e acusa também a coluna que existe no banco e não está declarada. O
pacote não lê o banco, então não vê esse caso: `description_gaps` é a lista das faltas **declaradas**, e
o portal não a apresenta como inventário físico. Quem garante que não há coluna materializada sem
declaração é a catraca, no `check` completo.

**Estado e evidência andam juntos.** O esquema recusa o estado sem a evidência que o sustenta: resultado
`pass`, `fail`, `warn` ou `error` sem `executed_at`; view `audited` sem *commit*, sem os três critérios
ou sem a referência; `not_audited` com qualquer um deles; `audit_pending_decision` sem achado. O que o
esquema não liga entre seções, o gerador confere: o `invocation_id` de cada resultado é o do
`run_results`, e `same_invocation_as_manifest` é verdadeiro só quando as duas execuções coincidem.

**Os três estados de um teste**, como o catálogo do BI pede: *declarado* (está em `tests`), *executado
com sucesso numa data* (`result.status = pass`, com `executed_at`) e *problema em aberto* (`fail`,
`warn` ou `error`). Os testes do `pytest` (invariantes, reconciliações, acesso) estão em `checks`, com o mesmo objeto de resultado.

**A guarda** (RVG-1-04): o `check-offline` recalcula o `inputs_sha256` a partir dos arquivos e recusa
o pacote atrasado. O pacote não cita o *commit* que o contém, porque esse *commit* ainda não existe
quando ele é gerado. O *commit* é o que o consumidor fixa. Um *commit* posterior que não mexe nos
insumos não invalida o pacote. O que o `check-offline` não vê, porque está fora do Git, tem duas
guardas (revisão do Bloco 4, RVB4-1-01 e 02):

- **o carimbo do *build*.** Todo comando do dbt que o `Makefile` roda e que escreve o *manifest*
  grava em `dbt/target/pacote_carimbo.json` o digest dos insumos do dbt (todo arquivo rastreado de
  `dbt/` e o glossário de `docs-paths`) lido antes e o `invocation_id` do *manifest* que **esse**
  comando escreveu — o que tem outra invocação que a de antes. O gerador recusa o *manifest* de outra
  execução ou de outros insumos: regerar sobre um *manifest* atrasado daria o digest de agora a um
  conteúdo antigo. O dbt rodado fora do `Makefile` não carimba, e o gerador recusa até o
  `make dbt-build`;
- **a 5ª etapa do `make check`**, depois do `pytest`: monta o pacote sem escrever e o compara com o
  versionado, fora os instantes, as execuções e o `tree_dirty_at_generation`. Resultado de teste ou de
  `pytest` que mudou, teste novo ou sumido, descrição nova: o pacote está atrasado, e o `check` falha
  até o `make catalog` e o *commit*.

**A sequência de publicação.** O pacote publica o resultado dos testes que o conferem, e por isso, depois
de mudar um insumo, ele se gera **duas** vezes: `make catalog` (insumos em dia; se a suíte mudou, o
JUnit anterior não é o dela, e `checks` sai vazio, com aviso), `make test` (o JUnit desses insumos),
`make catalog` de novo (o `checks` desse JUnit) e o *commit*. Com o `make check` no
lugar do `make test`, a 5ª etapa acusa o pacote da primeira geração, e o segundo `make catalog` é o que a
resolve.

---

## 4. O que a versão 1 não leva

Fica para campo novo, se um consumidor pedir:

- o texto dos documentos, dos ADRs e do glossário: o portal os lê por *commit*;
- os objetos tocados por cada item em aberto (`open_items.*.objects`), que nenhuma declaração diz hoje;
- as evidências do GCP, que estão fora do Git, no `mvp_eng_dados_1` (`environments`, `evidencias_gcp`).

---

## 5. O que se fecha na geração (Bloco 4)

O formato está fixado aqui. Na geração ficam a lista exata de `provenance.inputs`, a lista final de
`environments` e o desenho da procedência do armazém. Se algum deles pedir mudança de formato, ela
entra por este documento e pelo esquema, com aviso aos consumidores.
