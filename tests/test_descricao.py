"""Cobertura de descrição: uma catraca por camada, sobre o que existe no armazém.

A [Governança §5.1](../docs/governanca_de_dados.md#51-padrão-de-metadados) pede
descrição em toda coluna e `domain` e `owner` em todo modelo, e em 23/10/2026 a
medição (M17 do plano do `bi-como-codigo`) achou 26 de 477 colunas descritas em
`analytics`, 31 de 188 em `consumption` e nenhum dos 41 objetos dessas camadas com
`domain` e `owner`. A v1.1.0 deriva a descrição por transporte
(`models/descriptions.py`); o texto do que é calculado é escrito à mão, depois.

A catraca conta **faltas**, não percentuais (N42): por camada, quantas colunas
materializadas não têm descrição no manifest, quantas relações não têm descrição
(F32) e quantos objetos não têm `domain` e `owner`. O número tem de ser **igual** ao teto: uma coluna nova sem descrição
falha, e uma melhora também falha até o teto baixar no mesmo commit — é isso que
faz a catraca clicar. O inventário é o banco, como na de classificação: contar o
`.yml` deixaria passar a coluna que ninguém declarou.
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter, defaultdict

import pytest
from conftest import CAMADAS

from mvp_ed1.models import descriptions, sensitivity

pytestmark = pytest.mark.integracao

MANIFEST = sensitivity.MANIFEST

#: Colunas materializadas sem descrição, por camada — o medido na entrega da
#: etapa 1.7 (03/11/2026), já com a herança. Só baixa, e no mesmo commit da melhora.
#: Baixado em 03/11/2026 (etapa 1.8): o texto escrito das colunas que calculam leva `analytics` e
#: `consumption` a zero, como a etapa pede; as internas ficam no que sobra delas.
#: Baixado em 14/11/2026 (G06, Bloco 3 do plano da base dos consumidores): o texto das colunas que
#: calculam em `trusted`, `staging`, `quarantine` e nos *snapshots*; e as 39 da ponte do legado
#: (B1 e B3) pela declaração do RVG-1-01 (`TEXTOS_DA_PONTE`). Zero em todas as camadas.
TETO_SEM_DESCRICAO: dict[str, int] = {
    "raw": 0, "raw_legacy": 0, "staging": 0, "trusted": 0, "analytics": 0,
    "consumption": 0, "quarantine": 0, "snapshots": 0, "governance": 0,
}

#: Relações materializadas — tabela, view, fonte, seed e snapshot — sem descrição, por camada, contando
#: também a que existe no banco sem declaração nenhum `.yml`. O F32 do plano da reabertura mediu 123 no
#: pacote da `v2.1.0` (17/11/2026), e o Bloco 3 escreveu cada uma no dono declarativo dela: o
#: `table_meta` em `raw` e `raw_legacy`, o `.yml` do modelo nas outras. Zero em todas as camadas.
TETO_RELACOES_SEM_DESCRICAO: dict[str, int] = {
    "raw": 0, "raw_legacy": 0, "staging": 0, "trusted": 0, "analytics": 0,
    "consumption": 0, "quarantine": 0, "snapshots": 0, "governance": 0,
}

#: Objetos materializados (modelo, snapshot, seed) sem `domain` ou sem `owner`, por camada.
#: Baixado em 03/11/2026 (etapa 1.8, N46): `owner` por camada e `domain` da tabela conduzida.
TETO_SEM_DOMINIO: dict[str, int] = {
    "raw": 0, "raw_legacy": 0, "staging": 0, "trusted": 0, "analytics": 0,
    "consumption": 0, "quarantine": 0, "snapshots": 0, "governance": 0,
}


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not MANIFEST.exists():
        pytest.skip("sem dbt/target/manifest.json; rode `make dbt-build`")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _relacoes(manifest: dict) -> dict[tuple[str, str], dict]:
    saida = {}
    for no in list(manifest["nodes"].values()) + list(manifest["sources"].values()):
        if no["resource_type"] in ("model", "seed", "snapshot", "source"):
            saida[(no["schema"], no.get("alias") or no.get("identifier") or no["name"])] = no
    return saida


def _faltas(medido: dict[str, int], teto: dict[str, int], o_que: str) -> list[str]:
    erros = []
    for camada in CAMADAS:
        if medido.get(camada, 0) > teto[camada]:
            erros.append(f"{camada}: {medido.get(camada, 0)} {o_que}, acima do teto {teto[camada]}")
        elif medido.get(camada, 0) < teto[camada]:
            erros.append(f"{camada}: {medido.get(camada, 0)} {o_que} — melhorou: baixe o teto de {teto[camada]} para {medido.get(camada, 0)}")
    return erros


def test_colunas_sem_descricao_por_camada_no_teto(manifest, colunas_materializadas, record_property) -> None:
    relacoes = _relacoes(manifest)
    sem = Counter()
    exemplos = defaultdict(list)
    for schema, relacao, coluna in sorted(colunas_materializadas):
        no = relacoes.get((schema, relacao))
        texto = ((no or {}).get("columns", {}).get(coluna) or {}).get("description") or ""
        if not texto.strip():
            sem[schema] += 1
            exemplos[schema].append(f"{relacao}.{coluna}")
    for camada in CAMADAS:
        record_property(f"undescribed_{camada}", sem.get(camada, 0))
    erros = _faltas(sem, TETO_SEM_DESCRICAO, "colunas sem descrição")
    assert erros == [], "\n".join(e + (f"; p.ex. {exemplos[e.split(':')[0]][:5]}" if "acima" in e else "") for e in erros)


def test_relacoes_sem_descricao_por_camada_no_teto(manifest, colunas_materializadas, record_property) -> None:
    """F32: toda relação do armazém tem descrição; a que falta, ou que nenhum `.yml` declara, sai nomeada."""
    relacoes = _relacoes(manifest)
    sem: dict[str, list[str]] = defaultdict(list)
    for schema, relacao in sorted({(s, t) for s, t, _ in colunas_materializadas}):
        no = relacoes.get((schema, relacao))
        if no is None:
            sem[schema].append(f"{relacao} (sem declaração em `.yml` nenhum)")
        elif not (no.get("description") or "").strip():
            sem[schema].append(relacao)
    for camada in CAMADAS:
        record_property(f"undescribed_relations_{camada}", len(sem.get(camada, [])))
    erros = _faltas({c: len(v) for c, v in sem.items()}, TETO_RELACOES_SEM_DESCRICAO, "relações sem descrição")
    assert erros == [], "\n".join(e + (f": {', '.join(sem[e.split(':')[0]])}" if "acima" in e else "") for e in erros)


def test_objetos_sem_dominio_ou_dono_por_camada_no_teto(manifest, colunas_materializadas) -> None:
    """Governança §5.1: `domain` e `owner` em todo modelo. Fontes ficam de fora — a regra é do modelo."""
    existentes = {(s, t) for s, t, _ in colunas_materializadas}
    sem = Counter()
    for (schema, relacao), no in _relacoes(manifest).items():
        if no["resource_type"] == "source" or (schema, relacao) not in existentes:
            continue
        meta = {**(no.get("meta") or {}), **((no.get("config") or {}).get("meta") or {})}
        if not (meta.get("domain") and meta.get("owner")):
            sem[schema] += 1
    erros = _faltas(sem, TETO_SEM_DOMINIO, "objetos sem domain/owner")
    assert erros == [], "\n".join(erros)


def test_herdado_e_escrito_contados_a_parte(manifest, record_property) -> None:
    """O relatório separa o que veio por transporte do que alguém escreveu (N42)."""
    _, derivacao = sensitivity.load()
    textos = descriptions.derive_texts(manifest, derivacao)
    por_camada: dict[str, Counter] = defaultdict(Counter)
    for (schema, _, _), origem in textos.origin.items():
        por_camada[schema][origem] += 1
    for camada, contagem in sorted(por_camada.items()):
        record_property(f"descriptions_{camada}", dict(contagem))
    assert textos.problems == [], textos.problems[:5]
    assert sum(c["inherited"] + c["bridge"] + c["convention"] for c in por_camada.values()) > 0


def test_contraprovas_no_manifest_real(manifest) -> None:
    """A receita somada da P01 não herda — o texto dela é o escrito; o canal herda pela união com a ponte, pela dimensão e pela view;
    sem a declaração da ponte, a união deixa de herdar."""
    _, derivacao = sensitivity.load()
    textos = descriptions.derive_texts(manifest, derivacao)
    p01 = ("consumption", "monthly_revenue_by_channel_and_category")
    soma = p01 + ("net_revenue_amount",)
    # A soma tem o texto escrito para ela (etapa 1.8), nunca o da coluna somada.
    assert textos.origin[soma] == "written"
    assert textos.texts[soma] != textos.texts[("analytics", "fact_sales_order_item", "net_revenue_amount")]
    canal = textos.texts[("staging", "stg_retail__sales_channels", "sales_channel_name")]
    for chave in (("trusted", "sales_channels"), ("analytics", "dim_sales_channel"), p01):
        assert textos.texts[chave + ("sales_channel_name",)] == canal, chave

    disco = descriptions.disk_entries()
    ponte = disco["legado__sales_channels"]
    for coluna in ponte.columns.values():
        (coluna.get("meta") or {}).pop("description_from", None)
    sem_declaracao = descriptions.derive_texts(manifest, derivacao, disco=disco)
    # Desde o F32, `trusted.sales_channels` está num `.yml` à mão, com a marca de herdado: sem a declaração
    # da ponte, a coluna deixa de herdar, e o texto que ficou no `.yml` é acusado — o `--check` reprova —,
    # em vez de sumir calado do `_derived.yml`, como antes da promoção.
    assert sem_declaracao.origin.get(("trusted", "sales_channels", "sales_channel_name")) != "inherited"
    assert any(p.startswith("sales_channels.sales_channel_name: não transporta mais (upstream_blank)") for p in sem_declaracao.problems)
    assert any("sem `description_from`" in p for p in sem_declaracao.problems)


def test_texto_novo_a_montante_chega_a_quarentena_das_entregas(manifest) -> None:
    """RVB3-1-01: a sonda do revisor. Mudar, **só em memória**, o texto de
    `trusted.shipments.delivery_event_count` agenda o *patch* do `.yml` à mão da
    quarentena — antes o arquivo era tido por gerado e guardava o texto antigo."""
    _, derivacao = sensitivity.load(MANIFEST)
    disco = descriptions.disk_entries()
    fontes = descriptions.disk_sources()
    coluna = disco["shipments"].columns["delivery_event_count"]
    disco["shipments"].columns["delivery_event_count"] = {**coluna, "description": "Texto novo, só para a sonda."}
    textos = descriptions.derive_texts(manifest, derivacao, disco=disco, fontes=fontes)
    destino = disco["rejected_shipment_deliveries"].path
    assert textos.origin[("quarantine", "rejected_shipment_deliveries", "delivery_event_count")] == "inherited"
    assert textos.patches[destino]["rejected_shipment_deliveries"]["delivery_event_count"] == "Texto novo, só para a sonda."
