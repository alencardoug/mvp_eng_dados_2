"""A drenagem do ramo de alertas (D63): a expectativa, as confirmações e a espera.

Três níveis. A comparação é pura e leva as contraprovas da revisão do plano (RVRB-3-01 e RVRB-4-01).
O ramo de alertas roda de verdade no executor local do Beam, sobre um `TestStream`, com o publicador real
e um transporte simulado: é o oráculo de que a confirmação sai por painel, inclusive sem alerta e no
painel atrasado, e só depois da entrega. O publicador, sozinho, com a entrega que falha.
"""

from __future__ import annotations

import datetime as dt
import json

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.test_stream import TestStream
from apache_beam.transforms.window import TimestampedValue
from apache_beam.utils.timestamp import Timestamp

from mvp_ed1.streaming import drenagem, pipeline, transport

UTC = dt.timezone.utc
INICIO = dt.datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
JANELA = 60


def _t(segundos: float) -> dt.datetime:
    return INICIO + dt.timedelta(seconds=segundos)


# ── a expectativa ────────────────────────────────────────────────────────────


def test_a_janela_e_a_do_fixed_windows_alinhada_a_epoca():
    base = dt.datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    assert drenagem.indice_da_janela(base, 60) == int(base.timestamp()) // 60
    assert drenagem.indice_da_janela(base + dt.timedelta(seconds=59.999), 60) == drenagem.indice_da_janela(base, 60)
    assert drenagem.indice_da_janela(base + dt.timedelta(seconds=60), 60) == drenagem.indice_da_janela(base, 60) + 1


def test_o_instante_sem_fuso_e_utc():
    """O `to_utc_datetime()` do Beam devolve sem fuso; lido como hora local, a janela se deslocava."""
    sem_fuso = dt.datetime(2026, 11, 17, 12, 0)
    assert drenagem.indice_da_janela(sem_fuso, 60) == drenagem.indice_da_janela(sem_fuso.replace(tzinfo=UTC), 60)


def test_o_destino_ja_preenchido_nao_entra_na_expectativa():
    """RVRB-4-01: o que outra execução gravou entrou na semente e não gera painel."""
    antigo = (1, 1, _t(5), _t(-3600), 10)        # gravado antes do início desta execução
    novo = (2, 2, _t(65), _t(30), 11)
    retransmitido = antigo                       # a retransmissão é barrada no destino: a linha é a mesma

    esperado = drenagem.esperado([antigo, novo, retransmitido], inicio=INICIO, janela_segundos=JANELA)

    assert esperado == {(2, 2, drenagem.indice_da_janela(_t(65), JANELA)): 1}


def test_o_corte_limita_a_expectativa():
    linhas = [(1, 1, _t(1), _t(1), 5), (1, 1, _t(2), _t(2), 9)]
    assert sum(drenagem.esperado(linhas, inicio=INICIO, janela_segundos=JANELA, ate_seq=5).values()) == 1


# ── a comparação: as contraprovas ────────────────────────────────────────────

A_W1 = (1, 1, 100)
B_W2 = (2, 2, 101)


def test_a_ultima_janela_confirmada_nao_basta():
    """RVRB-3-01: a última janela confirmada e um par anterior retido — a espera continua."""
    d = drenagem.comparar({A_W1: 3, B_W2: 1}, {B_W2: 1})
    assert not d.drenado and d.faltam == [A_W1] and d.fechados == 1


def test_par_parcial_nao_fecha():
    d = drenagem.comparar({A_W1: 3}, {A_W1: 2})
    assert not d.drenado and d.faltam == [A_W1] and d.eventos_confirmados == 2


def test_confirmado_a_mais_nao_e_drenado():
    """Excedente quer dizer que a marca da execução e o painel não concordam: não se afirma drenagem."""
    assert not drenagem.comparar({A_W1: 1}, {A_W1: 2}).drenado
    assert not drenagem.comparar({}, {A_W1: 1}).drenado


def test_nada_inserido_e_drenado_de_imediato():
    """Sem inserção nesta execução, não há painel a esperar — e zero alerta é legítimo."""
    assert drenagem.comparar({}, {}).drenado


def test_o_prazo_esgotado_e_falha():
    relogio = iter(range(0, 100, 10))
    r = drenagem.aguardar(lambda: drenagem.comparar({A_W1: 1}, {}), prazo_s=30,
                          relogio=lambda: next(relogio), dormir=lambda _: None)
    assert not r.drenado and r.motivo == "prazo"


def test_o_pipeline_que_morre_encerra_a_espera():
    r = drenagem.aguardar(lambda: drenagem.comparar({A_W1: 1}, {}), vivo=lambda: False, dormir=lambda _: None)
    assert r.motivo == "morreu"


# ── as confirmações no diretório ─────────────────────────────────────────────


def test_cada_painel_conta_uma_vez_e_a_linha_incompleta_espera(tmp_path):
    janela = _t(0).replace(second=0)
    painel = {"janela_inicio": janela, "indice_do_painel": 0, "eventos": 2, "atrasado": False}
    c = drenagem.Confirmador(tmp_path)
    c.escrever(drenagem.confirmacao(painel, (1, 1)))
    c.escrever(drenagem.confirmacao(painel, (1, 1)))                     # o mesmo painel, reconfirmado
    c.escrever(drenagem.confirmacao({**painel, "indice_do_painel": 1, "eventos": 1}, (1, 1)))
    c.fechar()
    with (tmp_path / "confirmacoes-parcial.jsonl").open("w") as f:
        f.write('{"warehouse_id": 9')                                     # sendo escrita

    assert drenagem.confirmado(tmp_path, JANELA) == {(1, 1, drenagem.indice_da_janela(janela, JANELA)): 3}


def test_a_execucao_e_lida_pelo_ponteiro(tmp_path, monkeypatch):
    monkeypatch.setattr(drenagem, "RAIZ", tmp_path)
    aberta = drenagem.Execucao.abrir(JANELA, agora=INICIO)
    lida = drenagem.Execucao.ler()
    assert lida == aberta and lida.diretorio.parent == tmp_path


# ── o ramo de alertas de verdade, no executor local ──────────────────────────


class _ProdutorSimulado:
    def __init__(self, entrega_falha: bool):
        self._falha = entrega_falha
        self._pendentes = []

    def produce(self, topico, key, value, on_delivery):
        self._pendentes.append(on_delivery)

    def poll(self, _):
        return 0

    def flush(self, _prazo):
        for chamar in self._pendentes:
            chamar("falhou" if self._falha else None, None)
        self._pendentes = []
        return 0


def _publicador(diretorio, falha=False):
    destino = transport.PublicarAlerta(transport_config(), confirmacoes=str(diretorio))
    destino._fabricar = lambda: _ProdutorSimulado(falha)
    return destino


def transport_config():
    from mvp_ed1.streaming import config

    return config.carregar().transporte


def _evento(seq, armazem, sku, delta, segundos, snapshot=False):
    instante = _t(segundos)
    return {"movement_id": seq, "warehouse_id": armazem, "product_variant_id": sku, "quantity_delta": delta,
            "occurred_at": instante, "_do_snapshot": snapshot}


def _rodar(eventos_por_watermark, diretorio, limiar=10, semente=None):
    """O ramo 2 inteiro — janela, gatilho, saldo, alerta, publicação — sobre um `TestStream`."""
    from mvp_ed1.streaming import config

    import dataclasses

    fluxo = dataclasses.replace(config.carregar(), limiar_de_unidades=limiar)
    corrente = TestStream()
    for watermark, eventos in eventos_por_watermark:
        if eventos:
            corrente = corrente.add_elements([
                TimestampedValue(e, Timestamp.from_utc_datetime(e["occurred_at"])) for e in eventos])
        corrente = corrente.advance_watermark_to(Timestamp.from_utc_datetime(_t(watermark)))
    corrente = corrente.advance_watermark_to_infinity()
    with TestPipeline(options=pipeline.opcoes()) as p:
        novos = p | corrente
        pipeline.ramo_de_alerta(novos, fluxo, INICIO, semear=lambda _: list((semente or {}).items()),
                                publicar=beam.ParDo(_publicador(diretorio)))
    return fluxo.processamento.janela_segundos


def test_o_ramo_confirma_cada_painel_inclusive_sem_alerta_e_o_atrasado(tmp_path):
    eventos = [
        # A, janela 0: só snapshot — constrói o saldo, não alerta, e confirma.
        (30, [_evento(1, 1, 1, 50, 5, snapshot=True)]),
        # B, janela 1: de 0 a 20, cruza o limiar de 10 para cima — uma normalização, entregue, e depois
        # a confirmação.
        (150, [_evento(2, 2, 2, 15, 61), _evento(3, 2, 2, 5, 70)]),
        # B, janela 1 de novo, atrasado mas dentro do tolerado: painel atrasado, confirmado à parte.
        (400, [_evento(4, 2, 2, 1, 75)]),
    ]
    janela = _rodar(eventos, tmp_path)

    esperado = drenagem.esperado(
        [(e["warehouse_id"], e["product_variant_id"], e["occurred_at"], INICIO, e["movement_id"])
         for _, lote in eventos for e in lote], inicio=INICIO, janela_segundos=janela)
    assert drenagem.comparar(esperado, drenagem.confirmado(tmp_path, janela)).drenado

    linhas = [json.loads(l) for f in tmp_path.glob("confirmacoes-*.jsonl") for l in f.read_text().splitlines()]
    assert sorted((l["warehouse_id"], l["atrasado"], l["alerta"]) for l in linhas) == [
        (1, False, False), (2, False, True), (2, True, False)]


def test_a_entrega_que_falha_nao_confirma(tmp_path):
    destino = _publicador(tmp_path, falha=True)
    destino.setup()
    painel = {"janela_inicio": _t(0), "indice_do_painel": 0, "eventos": 1, "atrasado": False,
              "chave": (1, 1), "alerta": {"warehouse_id": 1, "product_variant_id": 1, "motivo": "abertura"}}
    with pytest.raises(RuntimeError, match="entrega"):
        list(destino.process(painel))
    destino.teardown()
    assert drenagem.confirmado(tmp_path, JANELA) == {}


# ── a restauração recomeça o grupo do Beam do início do log ──────────────────


def test_a_restauracao_recomeca_o_grupo_do_beam_do_inicio_do_log():
    """D63, segunda parte: em 04/10/2026 o grupo `mvp_ed1_beam` tinha o *offset* 6009 num tópico cujo
    *log* começava em 13700, estado deixado por uma restauração, e o Beam releu 13.700 mensagens.

    A restauração descarta o CDC no passo 3 com `stream-down FORCE=1`, que derruba a composição com o
    volume do Redpanda — tópicos e *offsets* dos grupos juntos —, antes do novo *snapshot* do passo 7.
    O consumidor do Beam, sem *offset*, começa do início do *log* novo.
    """
    import yaml

    from test_makefile import RAIZ, _receitas

    receitas = _receitas((RAIZ / "Makefile").read_text(encoding="utf-8"))
    passos = receitas["recovery-restore"]
    descarte = next(i for i, l in enumerate(passos) if "stream-down FORCE=1" in l)
    snapshot = next(i for i, l in enumerate(passos) if "medir CENARIO=streaming" in l)
    assert descarte < snapshot

    assert any("down $(if $(filter 1,$(FORCE)),-v)" in l for l in receitas["stream-down"])
    composicao = yaml.safe_load((RAIZ / "docker" / "docker-compose.streaming.yml").read_text(encoding="utf-8"))
    volumes = [v for s in composicao["services"].values() for v in s.get("volumes", [])]
    assert any(v.startswith("redpanda_data:") for v in volumes), "o estado do Redpanda num volume nomeado"
    assert "redpanda_data" in composicao["volumes"]

    fonte = (RAIZ / "src" / "mvp_ed1" / "streaming" / "transport.py").read_text(encoding="utf-8")
    assert '"auto.offset.reset": "earliest"' in fonte


# ── a expectativa lida do destino de verdade, só leitura ─────────────────────


@pytest.fixture(scope="module")
def armazem():
    import os

    from sqlalchemy import create_engine, text

    if not os.environ.get("WAREHOUSE_DB_PASSWORD"):
        pytest.skip("ambiente sem .env carregado; rode por `make test`")
    from mvp_ed1.db import WAREHOUSE, database_url

    motor = create_engine(database_url(WAREHOUSE))
    try:
        with motor.connect() as conexao:
            conexao.execute(text("select 1"))
    except Exception as erro:  # pragma: no cover — depende do ambiente
        motor.dispose()
        pytest.skip(f"PostgreSQL indisponível: {erro}")
    yield motor
    motor.dispose()


@pytest.mark.integracao
def test_a_expectativa_no_destino_separa_esta_execucao_das_anteriores(armazem, tmp_path):
    """O destino de hoje foi todo gravado por execuções passadas: para uma execução que começa agora, não
    há painel a esperar; para uma que começasse antes de tudo, todo o livro quente seria dela."""
    from sqlalchemy import text

    from mvp_ed1.streaming import config

    destino = config.carregar().destino.qualificado
    with armazem.connect() as conexao:
        total = conexao.execute(text(f"select count(*) from {destino}")).scalar_one()
    if not total:
        pytest.skip("destino quente vazio")

    agora = drenagem.Execucao(tmp_path, dt.datetime.now(UTC), JANELA)
    assert drenagem.medir_no_armazem(agora, ate_seq=None, destino=destino, motor=armazem).drenado

    antes = drenagem.Execucao(tmp_path, dt.datetime(2000, 1, 1, tzinfo=UTC), JANELA)
    d = drenagem.medir_no_armazem(antes, ate_seq=None, destino=destino, motor=armazem)
    assert d.eventos_esperados == total and not d.drenado and d.eventos_confirmados == 0
