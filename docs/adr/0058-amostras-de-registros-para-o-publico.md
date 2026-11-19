# ADR-0058 — Publicar amostras de registros num arquivo próprio, com o campo pessoal mascarado para o público anônimo

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 19/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | D95 ([Pendências](../pendencias.md)), aberta pela D06 do `gdados` |
| Substitui / é substituída por | — (complementa o [ADR-0049](0049-separar-a-classificacao-da-exposicao.md), sem substituí-lo) |

## Contexto

O Owner quer ver no portal `gdados` as cinco primeiras linhas de cada relação, com todas as colunas, como exemplo
de preenchimento. O `gdados` não lê banco: pediu pela caixa de correio, em 18/11/2026 (a D06 dele), que este
projeto **propusesse** uma exportação versionada, lida por *commit* fixado, como o pacote de metadados. O arquivo
iria ao repositório público daqui e ao site público do portal. A proposta está em
`data/medicoes/base_consumidores/avisos/resposta_gdados_20261119.md`, fora do Git.

Medido em leitura no armazém da `v2.2.0`, em 19/11/2026 (`data/medicoes/base_consumidores/amostras_d06/`):

- **282 relações** no pacote, e cinco linhas de cada uma, em JSON, somam **cerca de 690 KB**. O pacote tem 5,5 MB;
- **165 colunas `personal`**, em sete camadas;
- os ***payloads*** do legado (`original_payload`, `cleaned_payload`, `achados`, `findings`: 95 colunas JSON em
  `staging`, `trusted` e `quarantine`) levam a **linha inteira** do legado, com os campos pessoais dentro;
- **o que o gerador garante** (`generator/providers.py`): o e-mail é sempre de `example.com`, e o documento termina
  em `-SIN`, que nenhum CPF ou CNPJ real tem. **O que não garante:** o telefone tem o formato real do celular
  brasileiro, e o endereço usa logradouro, número e CEP plausíveis. Os dois podem coincidir com os de uma pessoa
  real, e "um dado sintético que reproduza um registro real deixa de ser sintético" (Governança §3).

O [ADR-0049](0049-separar-a-classificacao-da-exposicao.md) diz que classificar não é expor: com dado sintético, a
exposição é livre, e quem vê o quê é decidido por **concessão**, nunca por reclassificação. Um arquivo público é
uma concessão a qualquer pessoa. Faltava decidir qual.

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **Mascarar todo campo `personal` para o público anônimo, inclusive dentro dos *payloads*** (a escolhida) | É o que a fase GCP faz com *policy tags*: a classificação decide a máscara para quem não tem concessão. Nenhum telefone ou endereço real vaza. Regra simples de enunciar e de testar | A amostra mostra menos: nome, e-mail e documento também saem mascarados, embora não possam coincidir |
| Mascarar só o que pode ser real (telefone, logradouro, número, CEP) | Mostra o máximo | A regra fica pela garantia do gerador, não pela classificação; o telefone que os defeitos do legado injetam em outros campos pede busca por padrão em texto livre, fácil de errar |
| Expor tudo, como o ADR-0049 permite | Nada a construir | Telefone e endereço realistas num site público |
| Corrigir o gerador para telefone e endereço nunca serem reais, e expor | Corrige a causa | Uma regeneração declarada, com ciclo próprio |
| **Um arquivo próprio ao lado do pacote** (a escolhida) | O pacote continua metadado, no formato 1; a amostra muda com o dado, e o pacote com a declaração | Um segundo arquivo para fixar e validar |
| Um campo novo no pacote | Um arquivo só | Dado dentro do contrato de metadados, e o pacote mudando a cada *build* |
| **Na fase do ponto de reposição, com a *tag* dela** (a escolhida) | O `gdados` recebe tudo de uma vez; a exportação roda depois do *build* final, sem mexer no ciclo | Aumenta o escopo da fase |
| Numa fase própria depois | Fase menor | Outra *tag* e outro aviso logo em seguida |

## Decisão

As amostras de registros são publicadas em **`docs/amostras_de_registros.json`**, um arquivo próprio ao lado do
pacote de metadados, com o **campo `personal` mascarado** para o público anônimo, e entram na fase do ponto de
reposição.

- **O arquivo.** O cabeçalho traz o formato, o instante da exportação, o `built_from_commit` e o `invocation_id`
  de `governance.warehouse_provenance`, o ambiente, a `as_of_date` e a regra de máscara. A exportação **recusa**
  rodar se a procedência não for `verified`. Por relação: a contagem total de linhas, a ordem usada, as colunas
  na ordem declarada, até cinco linhas e as colunas mascaradas. Um esquema JSON ao lado, como o do pacote.
- **Quantas e quais.** Cinco por relação, das 282, com todas as colunas. "Primeiras" pela chave declarada, para o
  arquivo não oscilar: a `primary_key` onde houver; senão o `grain` e a `identity` de `view_rules`; senão as
  colunas do teste de unicidade da relação; senão todas as colunas na ordem declarada. Relação vazia entra com
  contagem zero.
- **A máscara.** Todo valor de coluna `sensitivity: personal` vira um marcador que diz o que foi omitido, sem
  conteúdo. Dentro dos *payloads* JSON do legado, a máscara alcança as chaves que são `personal` na relação de
  origem da linha, e também os achados que citam o valor de uma delas. O valor nulo continua nulo.
- **A prova da máscara**, um oráculo e não um argumento: nenhum valor não nulo de nenhuma coluna `personal` do
  armazém aparece em lugar nenhum do arquivo.
- **Fica fora:** nada. Os quatro objetos de `governance` entram: não guardam máquina nem pessoa.

## Consequências

- **Positivas:**
  - o portal mostra o preenchimento real de cada relação, por *commit* fixado, com a procedência do dado;
  - a máscara exercita a regra que a fase GCP impõe com *policy tags*, agora sobre um artefato público;
  - o pacote fica como está, no formato 1.
- **Negativas:**
  - a amostra mascara também o que não poderia coincidir (e-mail, documento, nome), e o portal não mostra a forma
    desses campos;
  - a máscara dentro dos *payloads* depende de saber a relação de origem de cada linha, e os achados do legado
    citam valores: a prova do oráculo é o que impede o vazamento, e ela precisa varrer o arquivo inteiro;
  - um arquivo a mais para regenerar, conferir e fixar a cada publicação, com guarda no `make check`;
  - as cinco linhas "primeiras" pela chave não escolhem os casos interessantes, como os defeitos do legado.
- **Paridade com o GCP:** a mesma exportação lê o BigQuery, com a máscara aplicada pelo exportador, pela mesma
  classificação. As *policy tags* da D79 **negam** a coluna marcada a quem não tem a concessão; não a mascaram.
  A contrapartida nativa da máscara é a política de mascaramento de dados sobre a *tag* `personal`, que a D79 não
  adotou e que fica como caminho, não como entrega. Nada disso é exercitado nesta fase: o GCP está desmontado (L9).
- **Documentos a atualizar** (com a implementação, na fase do ponto de reposição):
  - [Pacote de metadados](../pacote_de_metadados.md): o arquivo irmão, o esquema e a leitura por *commit*;
  - [Governança de Dados](../governanca_de_dados.md) §4: a concessão ao público anônimo, com a máscara;
  - [Consumidores](../consumidores.md) §5: a `prevista` do arquivo novo antes, a `feita` depois;
  - [Execução Local](../execucao_local.md): o alvo da exportação na sequência de publicação;
  - o README, no mapa da documentação.

## Retificação de 19/11/2026

O texto acima é o aceito em 19/11/2026 e não foi alterado. A revisão do
[plano da fase](../../PLANO_ponto_de_reposicao.md) (rodada 3, RVPR-3-01 a RVPR-3-06) mostrou cinco afirmações
erradas ou incompletas, e o Owner decidiu, no mesmo dia, como tratar o legado defeituoso. Ficam corrigidas aqui:

- **O legado defeituoso, por decisão do Owner.** O defeito `TEXT_DELIMITER` do legado faz um campo absorver os
  vizinhos: no lote `133e04d2…`, `support_agents`, linha 2, `agent_code = "AGT-0002;Renan;Costela"`, com os campos de
  nome vazios. A coluna é `internal`, e mascarar pela classificação não alcança esse conteúdo. Perguntado, o Owner
  decidiu **não mascará-lo e mostrar o defeito**: nas relações derivadas do legado, as linhas com defeito
  registrado (na classificação do legado ou no manifesto de injeção) **entram primeiro** na amostra, pela chave,
  e as limpas completam as cinco. O conteúdo deslocado aparece como está. Medido no manifesto: são três
  `TEXT_DELIMITER` no lote, e só esse carrega dado pessoal, um nome sintético. Nenhum telefone é deslocado para
  coluna não pessoal.
- **Os *payloads*.** "A máscara alcança as chaves que são `personal` na relação de origem da linha" fica assim: a
  estrutura do JSON é mantida, e cada folha cuja chave é `personal` na relação de origem vira marcador. A origem
  é a dependência declarada do modelo, em `stg_legacy__*`, e a coluna `source_table`, em `trusted.legacy_*` e em
  `quarantine.rejected_legacy_records`. As coleções de linhas (`payloads`, `last_payload`) são tratadas linha a
  linha. Em `findings`, o `original_value` e o `cleaned_value` de uma coluna `personal` viram marcador; `achados` e
  `value_findings` são mapas de códigos, sem valor. **Origem ou forma não resolvida vira marcador inteiro.**
- **A prova da máscara.** "Nenhum valor não nulo de nenhuma coluna `personal` aparece em lugar nenhum" não é
  executável: valores curtos (UF, número, `BR`) coincidem com campos públicos legítimos. A prova passa a ser **por
  ocorrência**: para cada célula e cada folha exportada, o esperado (marcador, nulo ou o valor da origem) é
  calculado de forma independente do exportador e comparado. Uma varredura complementar procura no arquivo os
  valores pessoais **fortes** das células mascaradas (e-mail, documento, telefone e nome completo), e os curtos
  ficam fora dela com o motivo escrito. O conteúdo deslocado mostrado por decisão do Owner é exceção listada, tirada
  do manifesto. As duas provas têm contraprova: um vazamento deliberado reprova, e uma coincidência curta legítima
  passa.
- **A cobertura.** "Das 282" é a medida de partida. O arquivo cobre **o conjunto de relações do pacote da mesma
  publicação**, e a guarda exige igualdade dos conjuntos. Com a `dim_sku_location` da Q75, são 283 previstas.
- **A procedência e a guarda.** A exportação continua recusando procedência que não seja `verified`. A conferência
  compara o arquivo com uma exportação refeita em memória, só leitura, **sem os campos de execução** (instante,
  invocação, *commit* do *build*), e exige que o *commit* do *build* registrado seja ancestral do atual sem mudança
  em código ou declaração desde então. Por isso ela sobrevive ao `dbt-build` do `make check`. A ordem da primeira
  publicação e da restauração está no plano.
- **A fase GCP.** "É o que a fase GCP faz com *policy tags*" (Alternativas) e "a máscara exercita a regra que a fase
  GCP impõe com *policy tags*" (Consequências) estão errados. As *policy tags* da D79 **negam** a coluna a quem não
  tem concessão; não a mascaram. A seção de Paridade já diz isso, e ela é que vale.
- **O nome.** Nas Consequências negativas, o nome está entre os valores que "não poderiam coincidir". Não é verdade:
  o gerador usa `faker: first_name` e `last_name`, sem marca de impossibilidade. Só o e-mail (`example.com`) e o
  documento (`-SIN`) têm essa garantia. A máscara já cobre o nome.
