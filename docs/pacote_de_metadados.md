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
| Estado | **Especificação.** O pacote ainda não é gerado: a geração é o Bloco 4 do [plano da base dos consumidores](../PLANO_base_dos_consumidores.md). Esta especificação veio antes da geração por decisão do Owner, em 14/11/2026 (Q13), para que os consumidores construam contra ela |
| Consumidores | `gdados` (E1) e `bi-como-codigo` (etapa 2.7): dois portais, um pacote (Q12, 14/11/2026) |
| Esquema | [`pacote_de_metadados.schema.json`](pacote_de_metadados.schema.json), JSON Schema 2020-12 |
| Exemplo | [`pacote_de_metadados.exemplo.json`](pacote_de_metadados.exemplo.json), validado pelo esquema no `check-offline` |

---

## 1. Os arquivos

| Arquivo | O que é | Desde |
|---|---|---|
| `docs/pacote_de_metadados.json` | O pacote. Gerado pelo `make catalog` e versionado | Bloco 4 (ainda não existe) |
| `docs/pacote_de_metadados.schema.json` | O esquema do formato. O pacote se valida contra o esquema **do mesmo commit** | 14/11/2026 |
| `docs/pacote_de_metadados.exemplo.json` | Um recorte ilustrativo, com valores copiados do *manifest* local de 13/11/2026 (`generated_at` 22:21:52Z, *invocation* `8eeff407…`). Não é regenerado e não substitui o pacote: os valores dele envelhecem com as correções dos Blocos 1 a 3. O `inputs_sha256` dele é um marcador (64 zeros) | 14/11/2026 |

---

## 2. O que o consumidor pode presumir

1. **Determinismo.** Mesmos insumos, mesmos bytes: UTF-8, chaves em ordem, listas em ordem,
   indentação de dois espaços e quebra de linha no fim. Nenhum carimbo de hora do próprio pacote:
   as datas são as dos artefatos de que ele nasce.
2. **Chave sempre presente.** Toda chave que o esquema declara aparece. A ausência de valor é
   `null`, e a lista vazia é `[]`. O portal mostra `null` como **ausente**, nunca como zero ou texto
   vazio. A exceção são os objetos `meta`, repassados do dbt como estão: as chaves deles são as que a
   declaração tem.
3. **Versão.** `format` é um inteiro. Campo novo não muda o número, e o consumidor ignora a chave
   que não conhece. Remover ou renomear um campo, ou mudar o significado dele, muda o número, e o
   aviso sai em [Consumidores §5](consumidores.md#5-o-que-mudou-para-quem-consome).
4. **Nada parcial.** Se falta o *manifest* ou o `run_results.json`, a geração falha e nenhum pacote é
   escrito. Não existe pacote "meio gerado".
5. **Texto como dado.** As descrições são Markdown em português, como estão no dbt. O consumidor as
   exibe como texto ou como Markdown saneado, sem executar HTML. Links relativos resolvem contra
   `provenance.link_base` (`docs/`), no commit fixado.
6. **Nada sensível.** Ficam de fora o SQL compilado, as mensagens de falha dos testes, os dados de
   conexão e os caminhos fora do repositório. A sensibilidade de cada coluna está no pacote, e o
   **dado** de nenhuma delas está.
7. **Identificadores.** Relação: `schema.nome`, como no `lineage --json`. Coluna:
   `schema.relação.coluna`. Pergunta: `P01` a `P16`. Teste: o `unique_id` do dbt.

---

## 3. Os campos

| Chave | O que traz | De onde vem |
|---|---|---|
| `format` | `1` | — |
| `provenance.inputs` e `provenance.inputs_sha256` | A lista dos arquivos rastreados pelo Git que alimentam o pacote e o SHA-256 do conteúdo deles, em ordem | Os arquivos, no momento da geração |
| `provenance.dbt` | Versão do dbt, adaptador, `generated_at` e `invocation_id` do *manifest* e do `run_results.json` | `dbt/target/` |
| `provenance.warehouse` | Que execução construiu o armazém. Na versão 1, sempre `not_verified` e `null` (L5) | Desenho do Bloco 4 |
| `provenance.link_base` | Contra onde resolvem os links relativos dos textos | — |
| `relations` | Cada *source*, *seed*, modelo e *snapshot*: tipo, materialização, descrição, `meta` (domínio, dono, escritores, retenção…) e as colunas, com descrição, tipo declarado, sensibilidade e `meta` | *Manifest* |
| `lineage` | A saída do `python -m mvp_ed1.models.lineage --json`, formato 1, **sem alteração**: por coluna, as folhas imediatas e as origens terminais, com o tipo (`source`, `seed`, `generated`) | `models/lineage.py` |
| `crossings` | As travessias que o dbt não vê (Airbyte, Debezium → Redpanda → Beam, captura do legado), com mecanismo e frequência, em Markdown | `lineage.crossings()` |
| `questions` | As 16 perguntas: título, fatos, medidas com a aditividade (`additive`, `semi_additive`, `non_additive`) e a nota, dimensões e view | [Perguntas de Negócio](glossario_de_negocio/perguntas_de_negocio.md) |
| `description_gaps` | Cada relação ou coluna **sem descrição**, explícita (`column: null` = falta a da relação). Em 13/11/2026 eram 141 colunas, a G06 | *Manifest*, pela mesma regra da catraca |
| `tests` | Cada teste de dados e teste de unidade do dbt: o que testa, o objeto e a coluna que guarda, onde está declarado e o resultado. `result: null` = **sem resultado**. O resultado traz o estado, a hora, a execução e se ela é a mesma do *manifest* (`same_invocation_as_manifest`) | *Manifest* e `run_results.json` |
| `view_audits` | Para cada uma das 16 views: o estado da auditoria do Bloco 1b (`not_audited`, `audited`, `audit_pending_decision`), o *commit* em que foi auditada, os critérios, o teste de referência e os achados | Declaração versionada do Bloco 1b. Até lá, todas `not_audited` |
| `environments` | A fonte da página de estrutura e ambientes, artefato por artefato: repositório, caminho, se é lido por *commit* ou não está disponível, e a data em que congelou (L4, L10) | Lista declarada no gerador |

**Os três estados de um teste**, como o catálogo do BI pede: *declarado* (está em `tests`), *executado
com sucesso numa data* (`result.status = pass`, com `executed_at`) e *problema em aberto* (`fail`,
`warn` ou `error`). Os testes do `pytest` (invariantes, reconciliações, acesso) não entram na versão 1.

**A guarda** (RVG-1-04): o `check-offline` recalcula o `inputs_sha256` a partir dos arquivos e recusa
o pacote atrasado. O pacote não cita o *commit* que o contém, porque esse *commit* ainda não existe
quando ele é gerado. O *commit* é o que o consumidor fixa. Um *commit* posterior que não mexe nos
insumos não invalida o pacote. O que o `check-offline` não vê, porque o *manifest* está fora do Git,
o `check` completo confere.

---

## 4. O que a versão 1 não leva

Fica para campo novo, se um consumidor pedir:

- a matriz de acesso (papéis × camadas) e a prova por execução, que hoje vivem na
  [Governança](governanca_de_dados.md) e no `tests/test_acesso.py`;
- os resultados do `pytest` e das reconciliações;
- as limitações e decisões em aberto, como a D66: o portal as lê nas
  [Pendências](pendencias.md), por *commit*;
- o texto dos documentos, dos ADRs e do glossário: o portal os lê por *commit*;
- as evidências do GCP, que estão fora do Git, no `mvp_eng_dados_1` (`environments`, `evidencias_gcp`).

---

## 5. O que se fecha na geração (Bloco 4)

O formato está fixado aqui. Na geração ficam a lista exata de `provenance.inputs`, a lista final de
`environments` e o desenho da procedência do armazém. Se algum deles pedir mudança de formato, ela
entra por este documento e pelo esquema, com aviso aos consumidores.
