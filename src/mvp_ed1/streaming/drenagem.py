"""A drenagem do ramo de alertas: o que o medidor espera antes de encerrar o Beam (D63).

Até 17/11/2026 o medidor esperava só o ramo 1 — o livro quente alcançar o corte (`espera.py`) — e
encerrava o *pipeline*. Os alertas saem do ramo 2, que só recebe painéis quando o *watermark* fecha as
janelas, e a contagem de alertas de uma medição dependia de quanto tempo sobrava (Pendências, D63,
medido em 04/10/2026). Nem o contador `alertas_emitidos` parado nem o *watermark* passando do maior
evento provam que o ramo terminou: o contador pode parar em zero sem nenhum painel processado, e o
*watermark* pode passar antes de a janela que o contém ser processada.

**O que prova, e como é medido.** O ramo de alertas recebe só o que o *sink* inseriu **nesta execução**:
os `novos` do `INSERT … ON CONFLICT DO NOTHING … RETURNING` (`sink.py`). O que já estava no destino entra
só na semente do saldo, sem painel. Então:

* **a expectativa** é a contagem, por par (armazém × SKU, janela de evento), das linhas do destino que
  esta execução gravou. A marca é a que já existe: `_stream_extracted_at`, carimbado pelo *sink* na
  gravação, a partir do instante em que o *pipeline* foi construído — o mesmo corte da semente (D62).
  Tudo o que entrou antes dele está na semente; tudo o que entrou depois chega pelo fluxo, uma vez só.
  A janela é a do `FixedWindows`, alinhada à época Unix: `floor(occurred_at / janela)`;
* **a confirmação** é escrita pelo publicador, por painel, depois de o alerta do painel (se houver) ter
  a entrega confirmada pelo transporte. Painel sem alerta também confirma, porque zero alerta é resultado
  legítimo. Ela leva a contagem de eventos do painel, e um par fecha quando a soma dos seus painéis
  (painéis atrasados incluídos, cada um contado uma vez pelo índice) iguala a esperada. A confirmação
  leva também os `movement_id` do painel, o delta, o saldo antes e depois dele e o ponto com que o painel ao vivo foi
  avaliado: é a fonte por painel do oráculo do alerta (plano do F36, Bloco 2), que a drenagem não lê.

Prazo esgotado é falha, nunca encerramento limpo. Um evento além do atraso tolerado é descartado pelo Beam
sem painel, e o par dele não fecha: a espera falha pelo prazo, e o evento nunca sai da expectativa.

**Na nuvem não há confirmação.** O *worker* do Dataflow não tem o diretório local, e a fase GCP está
desmontada desde 13/11/2026. O publicador do Pub/Sub só publica o alerta do painel.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

#: Onde cada execução local do *pipeline* deixa o seu registro e as confirmações. Fora do Git (`data/`).
RAIZ = pathlib.Path(__file__).resolve().parents[3] / "data" / "streaming" / "execucoes"

#: O arquivo que aponta para a execução mais recente, para quem chama a espera à mão.
ULTIMA = "ULTIMA"

Par = tuple[int, int, int]  # (warehouse_id, product_variant_id, índice da janela)


@dataclass(frozen=True)
class Execucao:
    """Uma execução local do *pipeline*: o diretório, o instante de construção e a janela."""

    diretorio: pathlib.Path
    inicio: dt.datetime
    janela_segundos: int

    @property
    def registro(self) -> pathlib.Path:
        return self.diretorio / "execucao.json"

    @classmethod
    def abrir(cls, janela_segundos: int, diretorio: str | os.PathLike | None = None,
              agora: dt.datetime | None = None) -> "Execucao":
        """Cria o diretório e grava o registro. O `inicio` é o corte da semente (D62)."""
        inicio = agora or dt.datetime.now(dt.timezone.utc)
        alvo = pathlib.Path(diretorio) if diretorio else RAIZ / inicio.strftime("%Y%m%dT%H%M%S%fZ")
        alvo.mkdir(parents=True, exist_ok=False)
        execucao = cls(alvo, inicio, janela_segundos)
        execucao.registro.write_text(json.dumps({
            "inicio": inicio.isoformat(), "janela_segundos": janela_segundos, "pid": os.getpid(),
        }), encoding="utf-8")
        ponteiro = alvo.parent / ULTIMA
        temporario = ponteiro.with_name(f".{ULTIMA}.{uuid.uuid4().hex}")
        temporario.write_text(str(alvo), encoding="utf-8")
        temporario.replace(ponteiro)
        return execucao

    @classmethod
    def ler(cls, diretorio: str | os.PathLike | None = None) -> "Execucao":
        """A execução de um diretório, ou a mais recente pelo ponteiro."""
        if diretorio:
            alvo = pathlib.Path(diretorio)
        else:
            ponteiro = RAIZ / ULTIMA
            if not ponteiro.exists():
                raise FileNotFoundError(f"nenhuma execução registrada em {RAIZ}: o pipeline subiu?")
            alvo = pathlib.Path(ponteiro.read_text(encoding="utf-8").strip())
        dado = json.loads((alvo / "execucao.json").read_text(encoding="utf-8"))
        return cls(alvo, dt.datetime.fromisoformat(dado["inicio"]), int(dado["janela_segundos"]))


def _utc(instante: dt.datetime) -> dt.datetime:
    """O instante em UTC. Sem fuso **é** UTC: é o que o `Timestamp.to_utc_datetime()` do Beam devolve.
    O `astimezone` de um instante sem fuso o leria como hora local, e a janela sairia deslocada pelo fuso
    da máquina (três horas aqui, medido no primeiro teste do ramo de alertas, 17/11/2026)."""
    return instante.replace(tzinfo=dt.timezone.utc) if instante.tzinfo is None else instante.astimezone(dt.timezone.utc)


def indice_da_janela(instante: dt.datetime, janela_segundos: int) -> int:
    """A janela do `FixedWindows(janela)` sem deslocamento: alinhada à época Unix, semiaberta."""
    return int(_utc(instante).timestamp() // janela_segundos)


def confirmacao(painel: Mapping[str, Any], chave: tuple[int, int]) -> dict[str, Any]:
    """A linha que o publicador escreve depois do painel — e do alerta dele — concluído."""
    return {
        "warehouse_id": chave[0],
        "product_variant_id": chave[1],
        "janela_inicio": _utc(painel["janela_inicio"]).isoformat(),
        "indice_do_painel": painel["indice_do_painel"],
        "eventos": painel["eventos"],
        "atrasado": painel["atrasado"],
        "alerta": painel.get("alerta") is not None,
        # Para o oráculo do alerta, não para a drenagem: a espera só lê a contagem.
        "movimentos": painel.get("movimentos"),
        "delta": painel.get("delta"),
        "ao_vivo": painel.get("ao_vivo"),
        "quantity_before": painel.get("quantity_before"),
        "quantity_on_hand": painel.get("quantity_on_hand"),
        "limiar": painel.get("limiar"),
    }


def composicao(painel: Mapping[str, Any], chave: tuple[int, int]) -> dict[str, Any]:
    """A composição do painel como a janela a emitiu, antes do saldo e do alerta (plano do F36, Bloco 2).

    É o registro independente com que o oráculo do alerta confere a composição que a confirmação declara:
    um painel fundido, dividido ou com movimento transferido depois da janela não bate com ele. A
    drenagem não o lê.
    """
    return {
        "warehouse_id": chave[0],
        "product_variant_id": chave[1],
        "janela_inicio": _utc(painel["janela_inicio"]).isoformat(),
        "indice_do_painel": painel["indice_do_painel"],
        "movimentos": list(painel["movimentos"]),
        "delta": painel["delta"],
        "eventos": painel["eventos"],
        "ao_vivo": painel["ao_vivo"],
    }


def entrada(painel: Mapping[str, Any], chave: tuple[int, int], ordem: int) -> dict[str, Any]:
    """A entrada do painel no acumulador, com a ordem dele no par, antes do saldo (plano do F36, Bloco 2).

    Com ela, o oráculo do alerta refaz o saldo de cada painel desde a semente na ordem em que esta execução os
    processou, e não numa ordem qualquer possível. A drenagem não a lê.
    """
    return {
        "warehouse_id": chave[0],
        "product_variant_id": chave[1],
        "janela_inicio": _utc(painel["janela_inicio"]).isoformat(),
        "indice_do_painel": painel["indice_do_painel"],
        "ordem": ordem,
        "movimentos": list(painel["movimentos"]),
    }


class Confirmador:
    """Um arquivo por instância do escritor: duas instâncias nunca escrevem no mesmo arquivo.

    `prefixo` separa as confirmações do publicador (`confirmacoes-*`, as da D63) dos registros que a espera não
    lê: a composição na saída da janela (`paineis-*`) e a entrada no acumulador, com a ordem (`entradas-*`).
    """

    def __init__(self, diretorio: str | os.PathLike, prefixo: str = "confirmacoes"):
        self._caminho = pathlib.Path(diretorio) / f"{prefixo}-{uuid.uuid4().hex}.jsonl"
        self._arquivo = None

    def escrever(self, linha: Mapping[str, Any]) -> None:
        if self._arquivo is None:
            self._arquivo = self._caminho.open("a", encoding="utf-8")
        self._arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
        # Sem `fsync`: quem lê está na mesma máquina, e o que importa é a linha chegar ao sistema
        # operacional antes de o publicador seguir.
        self._arquivo.flush()

    def fechar(self) -> None:
        if self._arquivo is not None:
            self._arquivo.close()
            self._arquivo = None


def esperado(linhas: Iterable[tuple[int, int, dt.datetime, dt.datetime, int]], *, inicio: dt.datetime,
             janela_segundos: int, ate_seq: int | None = None) -> dict[Par, int]:
    """Eventos por par que **esta execução** gravou: `_stream_extracted_at` a partir do `inicio`.

    `linhas` são `(warehouse_id, product_variant_id, occurred_at, _stream_extracted_at, event_sequence)`.
    O que outra execução gravou antes fica de fora: entrou na semente, e não gera painel.
    """
    contagem: dict[Par, int] = defaultdict(int)
    for armazem, sku, ocorrido, extraido, sequencia in linhas:
        if extraido < inicio or (ate_seq is not None and sequencia > ate_seq):
            continue
        contagem[(armazem, sku, indice_da_janela(ocorrido, janela_segundos))] += 1
    return dict(contagem)


def confirmado(diretorio: str | os.PathLike, janela_segundos: int) -> dict[Par, int]:
    """Eventos confirmados por par. Cada painel conta uma vez, pelo índice: uma reexecução do pacote
    que confirmasse o mesmo painel de novo não soma duas vezes. A última linha sem `\\n` está sendo
    escrita, e fica para a próxima leitura."""
    paineis: dict[tuple[int, int, int, int], int] = {}
    for arquivo in sorted(pathlib.Path(diretorio).glob("confirmacoes-*.jsonl")):
        texto = arquivo.read_text(encoding="utf-8")
        completas = texto[: texto.rfind("\n") + 1] if "\n" in texto else ""
        for linha in completas.splitlines():
            if not linha.strip():
                continue
            c = json.loads(linha)
            janela = indice_da_janela(dt.datetime.fromisoformat(c["janela_inicio"]), janela_segundos)
            paineis[(c["warehouse_id"], c["product_variant_id"], janela, c["indice_do_painel"])] = c["eventos"]
    soma: dict[Par, int] = defaultdict(int)
    for (armazem, sku, janela, _), eventos in paineis.items():
        soma[(armazem, sku, janela)] += eventos
    return dict(soma)


@dataclass
class Drenagem:
    """O ramo de alertas contra a expectativa: pares fechados, faltantes e a mais."""

    pares: int
    fechados: int
    eventos_esperados: int
    eventos_confirmados: int
    faltam: list[Par] = field(default_factory=list)
    excedentes: list[Par] = field(default_factory=list)

    @property
    def drenado(self) -> bool:
        return not self.faltam and not self.excedentes


def comparar(esperados: Mapping[Par, int], confirmados: Mapping[Par, int]) -> Drenagem:
    """Fecha o par que tem a contagem exata. Confirmado acima do esperado, ou par confirmado que não
    era esperado, é **excedente** e impede a drenagem: a marca da execução e o painel não concordam,
    e "drenado" diria mais do que se sabe."""
    faltam = sorted(p for p, n in esperados.items() if confirmados.get(p, 0) < n)
    excedentes = sorted(p for p, n in confirmados.items() if n > esperados.get(p, 0))
    return Drenagem(
        pares=len(esperados),
        fechados=sum(1 for p, n in esperados.items() if confirmados.get(p, 0) == n),
        eventos_esperados=sum(esperados.values()),
        eventos_confirmados=sum(min(confirmados.get(p, 0), n) for p, n in esperados.items()),
        faltam=faltam,
        excedentes=excedentes,
    )


@dataclass
class Resultado:
    drenado: bool
    motivo: str
    segundos: float
    ultimo: Drenagem


def aguardar(medir, *, prazo_s: float = 900.0, intervalo_s: float = 2.0, vivo=None, reportar=None,
             relogio=time.monotonic, dormir=time.sleep) -> Resultado:
    """Espera `medir()` devolver uma drenagem completa. Três desfechos, como a espera do livro:
    `drenado`, `prazo` e `morreu`."""
    comeco = relogio()
    ultimo = medir()
    while True:
        if reportar is not None:
            reportar(ultimo)
        if ultimo.drenado:
            return Resultado(True, "drenado", relogio() - comeco, ultimo)
        if vivo is not None and not vivo():
            return Resultado(False, "morreu", relogio() - comeco, ultimo)
        if relogio() - comeco >= prazo_s:
            return Resultado(False, "prazo", relogio() - comeco, ultimo)
        dormir(intervalo_s)
        ultimo = medir()


def medir_no_armazem(execucao: Execucao, *, ate_seq: int | None, destino: str, motor) -> Drenagem:
    """A expectativa lida do destino, só o que esta execução gravou; as confirmações, do diretório."""
    import sqlalchemy as sa

    with motor.connect() as conexao:
        linhas = conexao.execute(sa.text(
            f"select warehouse_id, product_variant_id, occurred_at, _stream_extracted_at, event_sequence "
            f"from {destino} where _stream_extracted_at >= :inicio"
        ), {"inicio": execucao.inicio}).all()
    return comparar(
        esperado(linhas, inicio=execucao.inicio, janela_segundos=execucao.janela_segundos, ate_seq=ate_seq),
        confirmado(execucao.diretorio, execucao.janela_segundos),
    )
