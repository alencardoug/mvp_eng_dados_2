# ADR-0053 — Medir a pontualidade numa fato no grão da remessa

| Campo | Informação |
|---|---|
| Estado | Aceita |
| Data | 14/11/2026 |
| Decisor | Owner principal |
| Decisão pendente resolvida | D66 |
| Substitui / é substituída por | — |

## Contexto

O [ADR-0033](0033-entrega-medida-em-dois-graos.md) mede a entrega em dois grãos: a pontualidade
(P13) pela **remessa**, o ciclo (P14) pelo **pedido**. A P13 lia `fact_shipment_item` e reduzia os
itens a remessa com `distinct`. Uma remessa sem item aceito não tinha linha para reduzir e ficava
fora do denominador, que o ADR-0033 define como "as remessas entregues".

Isso acontece no legado, por cascata: um produto com defeito próprio é rejeitado, e com ele as
variantes, os itens de pedido e os itens de remessa que dependem dele (ADR-0038). A remessa e o
pedido passam pelas regras e ficam em `trusted`. Na v1.0.0 eram 12 de 144 remessas legadas entregues
(M27 do `bi-como-codigo`). Remedido em 14/11/2026, antes da decisão: 16 de 147, 10,9%, todas com os
itens na quarentena e nenhum item aceito. O retail fecha 3.166 de 3.166.

A D66 ficou adiada na v1.1.0 e entrou na fase da base dos consumidores pela Q10 do
`PLANO_base_dos_consumidores.md`, porque a primeira publicação do `bi-como-codigo` leva a P13.

## Alternativas consideradas

| Alternativa | A favor | Contra |
|---|---|---|
| **Uma fato no grão da remessa, lida pela P13** | A pontualidade é atributo da remessa, e estas remessas passaram pelas regras: o que se rejeitou foi o conteúdo, três níveis acima. O denominador volta a ser o que o ADR-0033 diz | Uma tabela a mais em `analytics` (de 25 para 26), com declaração, testes e documentação. Duas fatos com atributos de remessa, que precisam não divergir |
| Emendar o ADR-0033: contar só a remessa com algum item aceito | Nenhuma tabela nova; só texto | A taxa da transportadora passa a depender de defeito de cadastro de produto, que nada tem com a entrega. 10,9% das entregas do legado somem da medida |
| Ler `trusted.shipments` direto na view | Nenhuma tabela nova | A view de consumo passaria a ler uma camada interna, contra o desenho das camadas (ADR-0016), e sem as dimensões conformadas |

## Decisão

**A P13 lê `fact_shipment`, uma fato com uma linha por remessa de `trusted.shipments`, inclusive a
que não tem item aceito.**

- Os atributos de remessa e de pedido saem dos mesmos modelos de `trusted` e com as mesmas
  expressões da `fact_shipment_item`, e a fato se reconcilia com `trusted.shipments` por teste
  (contagem e tentativas de entrega).
- A `fact_shipment_item` continua: é ela que diz o que foi enviado. A P14 continua nela.
- A P13 tem um teste de população: por mês de chegada, a soma das remessas entregues da view é a de
  `trusted.shipments`.

## Consequências

- **Positivas:** o denominador da P13 é o do ADR-0033, e a limitação documentada sai da view. A
  primeira publicação do `bi-como-codigo` não leva um número que se sabe recortado.
- **Negativas:** 26 tabelas em `analytics`, e duas fatos que repetem atributos de remessa: a
  divergência entre elas é risco aceito, coberto pelo teste de reconciliação de cada uma com
  `trusted.shipments`. Os valores da P13 mudam no legado (3.297 → 3.313 remessas entregues no total).
  A importação do `nl_sql`, congelada em 25 tabelas, não recebe esta fato.
- **Paridade com o GCP:** a mesma tabela no BigQuery, materializada como as outras fatos de
  `analytics` (ADR-0016). Nada de específico do PostgreSQL.
- **Documentos a atualizar:** o [Modelo de Dados](../modelo_de_dados.md) §3; o
  [glossário de entrega no prazo](../glossario_de_negocio/entrega_no_prazo.md); as
  [Perguntas de Negócio](../glossario_de_negocio/perguntas_de_negocio.md) (P13); as
  [Pendências](../pendencias.md) (D66); os [Consumidores](../consumidores.md) §5.
