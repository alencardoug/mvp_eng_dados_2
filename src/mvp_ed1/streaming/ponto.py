"""A fotografia do ponto de reposição que o alerta usa (ADR-0057 e a retificação dele).

O ponto de cada par armazém/SKU é do dbt (`analytics.dim_sku_location`). O alerta não guarda limiar
próprio: o **lançador** lê o ponto uma vez por execução, guarda a leitura com a execução e a entrega
pelo construtor a todas as instâncias do `AcumularSaldoEAlertar`. Ler no `setup` de cada instância
daria pontos diferentes a instâncias criadas antes e depois de um *build*, dentro da mesma execução
(RVPR-1-03).

**Dois modos, e nenhum terceiro.**

- `fotografia`: o ponto lido do armazém. A relação ausente, ilegível ou vazia **para o lançamento**:
  um alerta avaliado contra ponto nenhum seria um alerta errado e calado. O par ausente da
  fotografia tem ponto zero: sem venda medida, não há o que repor.
- `carga`: sem fotografia, pedido explicitamente por quem roda antes do *build* (o passo 7 da
  restauração, a publicação sem produtor), quando o modelo ainda não existe ou é o do estado que está
  sendo substituído (Q79). O *snapshot* não alerta por desenho; um painel **ao vivo** nesse modo faz a
  execução falhar, em vez de ser avaliado.

A leitura é feita com a credencial de quem lança (o login do `.env`; na nuvem, a ADC), como todo
componente hoje (Governança §7). A concessão ao `streamer` na relação declara a dependência e é provada
assumindo o papel; ela não é a identidade desta leitura.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

FOTOGRAFIA = "fotografia"
CARGA = "carga"

#: O nome do arquivo da fotografia no diretório da execução (`drenagem.Execucao`).
ARQUIVO = "ponto_de_reposicao.json"


class PontoIndisponivel(RuntimeError):
    """A relação do ponto não pôde ser lida, ou veio vazia: o lançamento para."""


class PainelAoVivoNaCarga(RuntimeError):
    """Um painel com evento ao vivo chegou numa execução de carga, que não tem ponto para avaliá-lo."""


@dataclass(frozen=True)
class Fotografia:
    """O ponto de cada par, fixo para a execução inteira. Imutável e serializável com o `DoFn`."""

    modo: str
    pontos: tuple[tuple[int, int, int], ...] = ()
    relacao: str | None = None
    lido_em: str | None = None
    _mapa: dict[tuple[int, int], int] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.modo not in (FOTOGRAFIA, CARGA):
            raise ValueError(f"modo desconhecido: {self.modo!r}")
        if self.modo == CARGA and self.pontos:
            raise ValueError("a carga não tem fotografia")
        object.__setattr__(self, "_mapa", {(w, v): p for w, v, p in self.pontos})

    @property
    def carga(self) -> bool:
        return self.modo == CARGA

    def ponto(self, armazem: int, sku: int) -> int:
        """O ponto do par; zero para o par que a fotografia não tem."""
        if self.carga:
            raise PainelAoVivoNaCarga(
                f"par ({armazem}, {sku}): painel ao vivo numa execução de carga, sem ponto de reposição"
            )
        return self._mapa.get((armazem, sku), 0)

    @property
    def sha256(self) -> str:
        corpo = json.dumps([list(t) for t in self.pontos], separators=(",", ":"))
        return hashlib.sha256(corpo.encode()).hexdigest()

    def registro(self) -> dict:
        return {
            "modo": self.modo,
            "relacao": self.relacao,
            "lido_em": self.lido_em,
            "pares": len(self.pontos),
            "sha256": self.sha256 if not self.carga else None,
            "pontos": [list(t) for t in self.pontos],
        }

    def guardar(self, diretorio: str | Path) -> Path:
        """Guarda a fotografia com a execução: é dela que o oráculo do alerta lê o ponto de cada par."""
        caminho = Path(diretorio) / ARQUIVO
        caminho.write_text(json.dumps(self.registro(), ensure_ascii=False, indent=1), encoding="utf-8")
        return caminho


def de_linhas(linhas: Iterable[tuple[int, int, int]], relacao: str, lido_em: dt.datetime) -> Fotografia:
    """Monta a fotografia; vazia é erro, porque um modelo vazio não é um modelo sem demanda."""
    pontos = tuple(sorted((int(w), int(v), int(p)) for w, v, p in linhas))
    if not pontos:
        raise PontoIndisponivel(f"{relacao}: nenhuma linha do varejo; o lançamento para")
    return Fotografia(FOTOGRAFIA, pontos, relacao, lido_em.isoformat())


def carga() -> Fotografia:
    return Fotografia(CARGA)


def consulta(relacao: str) -> str:
    """O par do varejo e o ponto dele. O caminho quente só transporta o varejo (Origem Legada §6)."""
    return (
        f"select warehouse_natural_key, product_natural_key, reorder_point from {relacao} "
        "where source_system = :origem order by 1, 2"
    )


def ler_local(relacao: str, origem: str, motor=None) -> Fotografia:
    """Lê a fotografia do armazém local, com a conexão do `.env`."""
    import sqlalchemy as sa

    from mvp_ed1.streaming.sink import engine

    proprio = motor is None
    motor = motor or engine()
    agora = dt.datetime.now(dt.timezone.utc)
    try:
        with motor.connect() as conexao:
            linhas = conexao.execute(sa.text(consulta(relacao)), {"origem": origem}).all()
    except sa.exc.SQLAlchemyError as erro:
        raise PontoIndisponivel(f"{relacao}: {erro.__class__.__name__}: {erro}") from erro
    finally:
        if proprio:
            motor.dispose()
    return de_linhas(linhas, relacao, agora)


def mapa(fotografia: Fotografia) -> Mapping[tuple[int, int], int]:
    """Só leitura, para o oráculo e os testes."""
    return dict(fotografia._mapa)
