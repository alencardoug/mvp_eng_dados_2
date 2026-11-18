"""Interface de linha de comando do caminho quente.

Os verbos que o `Makefile` chama. Nenhum deles decide nada: janela, atraso,
limiar e modo de *snapshot* estão nos arquivos declarativos de `streaming/`, e
mudá-los é editar a declaração, que é o que se revisa.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from mvp_ed1.streaming import config as cfg

LOG = logging.getLogger("streaming")

CONNECT_URL = os.environ.get("KAFKA_CONNECT_URL", "http://localhost:8083")

_VARIAVEL = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


# ── Conector ────────────────────────────────────────────────────────────────
def _resolver(valor: Any) -> Any:
    """Substitui `${VAR}` pelo ambiente. Falta de variável é erro, não vazio."""
    if not isinstance(valor, str):
        return valor

    def troca(m: re.Match) -> str:
        nome = m.group(1)
        if nome not in os.environ:
            raise SystemExit(
                f"ERRO: variável {nome} ausente do ambiente, exigida por "
                "streaming/connectors/. Use os alvos do Makefile, que carregam o .env."
            )
        return os.environ[nome]

    return _VARIAVEL.sub(troca, valor)


def declaracao_do_conector(caminho: Path) -> dict[str, Any]:
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return {"name": bruto["name"], "config": {k: _resolver(v) for k, v in bruto["config"].items()}}


def _connect(metodo: str, rota: str, corpo: Any = None) -> Any:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        f"{CONNECT_URL}{rota}", data=dados, method=metodo,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            texto = r.read().decode()
            return json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode()
        raise SystemExit(f"ERRO {e.code} do Kafka Connect em {metodo} {rota}: {detalhe}") from None
    except urllib.error.URLError as e:
        raise SystemExit(
            f"ERRO: Kafka Connect não responde em {CONNECT_URL} ({e.reason}). "
            "Rode 'make stream-up'."
        ) from None


def comando_conector(args) -> int:
    """Aplica todas as declarações de `streaming/connectors/`.

    `PUT .../config` é criar-ou-atualizar: aplicar duas vezes não duplica nem
    reinicia o que já está correto. É o que o ADR-0020 foi buscar no Kafka
    Connect — reconfigurar sem derrubar.
    """
    for caminho in sorted(cfg.CONECTORES.glob("*.yml")):
        declaracao = declaracao_do_conector(caminho)
        nome = declaracao["name"]
        _connect("PUT", f"/connectors/{nome}/config", declaracao["config"])
        print(f"conector {nome!r} aplicado a partir de {caminho.name}")
    return 0


def comando_status(args) -> int:
    conectores = _connect("GET", "/connectors") or []
    if not conectores:
        print("nenhum conector registrado. Rode 'make stream-connector'.")
        return 1
    falhou = False
    for nome in conectores:
        estado = _connect("GET", f"/connectors/{nome}/status")
        conector = estado["connector"]["state"]
        print(f"{nome}: conector={conector}")
        for tarefa in estado.get("tasks", []):
            print(f"  tarefa {tarefa['id']}: {tarefa['state']}")
            if tarefa["state"] == "FAILED":
                falhou = True
                print("    " + (tarefa.get("trace") or "").strip().splitlines()[0])
        falhou = falhou or conector == "FAILED"
    return 1 if falhou else 0


def comando_remover_conector(args) -> int:
    for nome in _connect("GET", "/connectors") or []:
        _connect("DELETE", f"/connectors/{nome}")
        print(f"conector {nome!r} removido")
    return 0


# ── Transporte ──────────────────────────────────────────────────────────────
def comando_duplicar(args) -> int:
    """Injeta duplicatas **no transporte**, republicando mensagens já entregues.

    O ADR-0019 foi explícito: idempotência sem teste que injeta duplicata é
    apenas intenção. Isto é o teste. A origem não é tocada — a duplicata real
    nasce no caminho, e é lá que ela é simulada (Geração §6).
    """
    from confluent_kafka import Producer

    from mvp_ed1.streaming.transport import consumidor

    fluxo = cfg.carregar()
    c = consumidor(fluxo.transporte, grupo=f"{fluxo.transporte.grupo_de_consumo}_duplicador",
                   **{"auto.offset.reset": "earliest"})
    p = Producer({"bootstrap.servers": fluxo.transporte.bootstrap})
    c.subscribe([fluxo.transporte.topico_de_eventos])

    repetidas = 0
    try:
        while repetidas < args.quantas:
            m = c.poll(5.0)
            if m is None:
                break
            if m.error() or m.value() is None:
                continue
            p.produce(fluxo.transporte.topico_de_eventos, key=m.key(), value=m.value())
            repetidas += 1
        p.flush(30)
    finally:
        c.close()
    print(f"{repetidas} mensagens republicadas em {fluxo.transporte.topico_de_eventos}")
    return 0


def comando_alertas(args) -> int:
    """Lê o tópico de alerta desde o início e resume o que foi emitido."""
    from mvp_ed1.streaming.transport import consumidor

    fluxo = cfg.carregar()
    c = consumidor(fluxo.transporte, grupo=f"{fluxo.transporte.grupo_de_consumo}_alertas_{args.grupo}")
    from confluent_kafka import TopicPartition

    c.assign([TopicPartition(fluxo.transporte.topico_de_alertas, 0, 0)])
    alertas: list[dict] = []
    while True:
        m = c.poll(3.0)
        if m is None:
            break
        if m.error() or m.value() is None:
            continue
        alertas.append(json.loads(m.value()))
    c.close()

    aberturas = [a for a in alertas if a["motivo"] == "abertura"]
    correcoes = [a for a in alertas if a.get("correcao_de_evento_atrasado")]
    print(f"tópico {fluxo.transporte.topico_de_alertas}: {len(alertas)} alertas")
    print(f"  aberturas (cruzaram o limiar de {fluxo.limiar_de_unidades} para baixo): {len(aberturas)}")
    print(f"  normalizações (voltaram acima): {len(alertas) - len(aberturas)}")
    print(f"  correções de evento atrasado: {len(correcoes)}")
    for a in alertas[: args.mostrar]:
        marca = " [correção de atraso]" if a.get("correcao_de_evento_atrasado") else ""
        print(
            f"  {a['motivo']:13} armazém {a['warehouse_id']} SKU {a['product_variant_id']:4} "
            f"saldo {a['quantity_before']} -> {a['quantity_on_hand']}{marca}"
        )
    return 0


# ── Produtor e pipeline ─────────────────────────────────────────────────────
def comando_produzir(args) -> int:
    from mvp_ed1.streaming.producer import ProdutorDeEventos

    fluxo = cfg.carregar()
    produtor = ProdutorDeEventos(fluxo.produtor, semente=args.semente, teto=args.limite)
    inicio = dt.datetime.now(dt.timezone.utc)
    relatorio = produtor.executar()
    duracao = (dt.datetime.now(dt.timezone.utc) - inicio).total_seconds()

    print(f"{relatorio.emitidos} eventos emitidos em {duracao:.1f}s "
          f"({relatorio.emitidos / max(duracao, 0.001):.0f}/s)")
    print(f"  atrasados de propósito: {relatorio.atrasados}")
    print(f"  transferências (pares):  {relatorio.transferencias}")
    for tipo, quantos in sorted(relatorio.por_tipo.items()):
        print(f"  {tipo:18} {quantos}")
    return 0


def comando_pipeline(args) -> int:
    from mvp_ed1.streaming.pipeline import executar

    fluxo = cfg.carregar()
    try:
        executar(fluxo, execucao_dir=args.execucao)
    except KeyboardInterrupt:
        print("\npipeline interrompido. O offset confirmado retoma de onde parou.")
        _sair_sem_finalizar(_threads_no_encerramento())
    return 0


#: Quanto o encerramento espera as *threads daemon* do Beam terminarem, em segundos, somadas.
PRAZO_DAS_THREADS = 10.0


def _sair_sem_finalizar(vivas, *, prazo_s: float = PRAZO_DAS_THREADS, sair=None) -> None:
    """A correção da V6, pela causa medida em 17/11/2026 (`medir CENARIO=streaming`, sem produtor).

    No SIGINT, onze *threads daemon* do Beam continuam vivas — os leitores gRPC e o *worker* LOOPBACK do
    Prism, que roda neste processo —, e escrevem *tracebacks* de "Socket closed" no `stderr` enquanto o
    Prism é destruído. O interpretador começava a desligar com uma delas segurando a trava do `stderr`, e
    abortava: "Fatal Python error: _enter_buffered_busy", código 134, núcleo gravado.

    Daí a ordem: esperar as *threads* com prazo, esvaziar `stdout`, `stderr` e os *handlers* de log, e sair
    com `os._exit(0)`, que não passa pela finalização. Nada se perde: o *sink* grava cada lote numa
    transação e confirma o *offset* depois dela, cada alerta é entregue antes da confirmação do painel,
    e o `with beam.Pipeline` já saiu.
    """
    import os as _os
    import time as _time

    fim = _time.monotonic() + prazo_s
    for thread in vivas:
        thread.join(max(0.0, fim - _time.monotonic()))
    restantes = [t.name for t in vivas if t.is_alive()]
    if restantes:
        LOG.info("V6: %d thread(s) ainda vivas depois de %.0fs; saindo sem finalizar: %s",
                 len(restantes), prazo_s, ", ".join(restantes))
    logging.shutdown()
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.flush()
        except Exception:  # noqa: BLE001 — sair é o que importa aqui
            pass
    (sair or _os._exit)(0)


def _threads_no_encerramento() -> list:
    """A medida da V6: o que fica vivo quando o *pipeline* devolve o controle.

    No ciclo de 17/11/2026 o Python abortava depois da mensagem acima, ao desligar o interpretador,
    porque uma *thread daemon* segurava o `stderr` ("_enter_buffered_busy … possibly due to daemon
    threads"). Antes de corrigir, mede-se quem é: o nome de cada *thread* ainda viva, e se é *daemon*.
    """
    import threading

    vivas = [t for t in threading.enumerate() if t is not threading.main_thread()]
    LOG.info(
        "V6: %d thread(s) vivas no encerramento%s", len(vivas),
        (": " + ", ".join(f"{t.name}{' [daemon]' if t.daemon else ''}" for t in vivas)) if vivas else "",
    )
    return vivas


# ── Fim declarado para o caminho quente ─────────────────────────────────────
def comando_corte(_args: argparse.Namespace) -> int:
    from mvp_ed1.streaming import espera

    print(espera.corte_da_origem())
    return 0


def _vigia(pid: int | None):
    """O predicado "o pipeline ainda está vivo", ou `None` sem PID."""
    import os as _os

    if pid is None:
        return None

    def vivo() -> bool:  # noqa: D401 — predicado, não descrição
        try:
            _os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            return False
        return True

    return vivo


def comando_aguardar(args: argparse.Namespace) -> int:
    """Espera o livro alcançar o corte; imprime o progresso a cada leitura."""
    from mvp_ed1.streaming import espera

    vivo = _vigia(args.pid)

    def reportar(f: espera.Faltantes) -> None:
        LOG.info(
            "livro %d/%d até a sequência %d — faltam %d%s",
            f.livro, f.origem, args.ate_seq, f.faltam,
            f" (ex.: {', '.join(f.exemplos)})" if f.exemplos else "",
        )

    r = espera.aguardar(
        args.ate_seq, prazo_s=args.prazo, intervalo_s=args.intervalo,
        vivo=vivo, reportar=reportar,
    )
    if r.alcancado:
        print(
            f"livro alcançou a sequência {args.ate_seq}: {r.ultimo.livro} eventos "
            f"em {r.segundos:.1f}s"
            + (f"; {r.ultimo.intrusas} chaves no livro que a origem não tem" if r.ultimo.intrusas else "")
        )
        return 0
    motivo = {
        "prazo": f"prazo de {args.prazo:.0f}s esgotado",
        "morreu": f"o pipeline (PID {args.pid}) morreu sob a espera",
    }[r.motivo]
    print(
        f"ERRO: {motivo} — faltam {r.ultimo.faltam} de {r.ultimo.origem} eventos "
        f"até a sequência {args.ate_seq}.",
        file=sys.stderr,
    )
    return 1


def comando_drenar(args: argparse.Namespace) -> int:
    """Espera o ramo de alertas confirmar cada painel do que esta execução gravou (D63)."""
    from mvp_ed1 import db
    from mvp_ed1.streaming import drenagem, espera

    execucao = drenagem.Execucao.ler(args.execucao)
    motor = espera._motor(db.WAREHOUSE)
    destino = cfg.carregar().destino.qualificado

    def reportar(d: drenagem.Drenagem) -> None:
        LOG.info("ramo de alertas: %d/%d pares fechados, %d/%d eventos confirmados%s",
                 d.fechados, d.pares, d.eventos_confirmados, d.eventos_esperados,
                 f"; {len(d.excedentes)} par(es) confirmados a mais" if d.excedentes else "")

    r = drenagem.aguardar(
        lambda: drenagem.medir_no_armazem(execucao, ate_seq=args.ate_seq, destino=destino, motor=motor),
        prazo_s=args.prazo, intervalo_s=args.intervalo, vivo=_vigia(args.pid), reportar=reportar,
    )
    if r.drenado:
        print(f"ramo de alertas drenado: {r.ultimo.pares} pares e {r.ultimo.eventos_esperados} eventos desta "
              f"execução confirmados em {r.segundos:.1f}s ({execucao.diretorio})")
        return 0
    motivo = {
        "prazo": f"prazo de {args.prazo:.0f}s esgotado",
        "morreu": f"o pipeline (PID {args.pid}) morreu sob a espera",
    }[r.motivo]
    exemplos = ", ".join(map(str, (r.ultimo.faltam or r.ultimo.excedentes)[:3]))
    print(f"ERRO: {motivo} — {r.ultimo.fechados} de {r.ultimo.pares} pares fechados, "
          f"{len(r.ultimo.excedentes)} confirmados a mais (ex.: {exemplos}). O ramo de alertas não drenou.",
          file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(prog="mvp_ed1.streaming", description=__doc__)
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("connector", help="aplica as declarações de streaming/connectors/").set_defaults(
        func=comando_conector
    )
    sub.add_parser("status", help="estado do conector e das tarefas").set_defaults(func=comando_status)
    sub.add_parser("connector-rm", help="remove os conectores registrados").set_defaults(
        func=comando_remover_conector
    )

    d = sub.add_parser("duplicar", help="republica mensagens no transporte (teste de idempotência)")
    d.add_argument("--quantas", type=int, default=50)
    d.set_defaults(func=comando_duplicar)

    a = sub.add_parser("alertas", help="lê e resume o tópico de alerta")
    a.add_argument("--mostrar", type=int, default=10)
    a.add_argument("--grupo", default="1")
    a.set_defaults(func=comando_alertas)

    pr = sub.add_parser("produzir", help="emite eventos novos no livro da origem")
    pr.add_argument("--semente", type=int, default=20260904)
    pr.add_argument("--limite", type=int, default=None)
    pr.set_defaults(func=comando_produzir)

    pl = sub.add_parser("pipeline", help="sobe o pipeline Beam")
    pl.add_argument("--execucao", default=None,
                    help="diretório da execução (D63); sem ele, um novo em data/streaming/execucoes/")
    pl.set_defaults(func=comando_pipeline)

    sub.add_parser(
        "corte", help="imprime o max(event_sequence) da origem — o fim de uma medição"
    ).set_defaults(func=comando_corte)

    ag = sub.add_parser("aguardar", help="espera o livro quente alcançar um corte")
    ag.add_argument("--ate-seq", type=int, required=True)
    ag.add_argument("--prazo", type=float, default=900.0, help="segundos")
    ag.add_argument("--intervalo", type=float, default=2.0, help="segundos entre leituras")
    ag.add_argument(
        "--pid", type=int, default=None,
        help="PID do pipeline; se ele morrer, a espera falha em vez de esgotar o prazo",
    )
    ag.set_defaults(func=comando_aguardar)

    dr = sub.add_parser("drenar", help="espera o ramo de alertas confirmar o que esta execução gravou (D63)")
    dr.add_argument("--execucao", default=None, help="diretório da execução; sem ele, a mais recente")
    dr.add_argument("--ate-seq", type=int, default=None)
    dr.add_argument("--prazo", type=float, default=900.0, help="segundos; esgotado é falha")
    dr.add_argument("--intervalo", type=float, default=2.0, help="segundos entre leituras")
    dr.add_argument("--pid", type=int, default=None, help="PID do pipeline; se ele morrer, a espera falha")
    dr.set_defaults(func=comando_drenar)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
