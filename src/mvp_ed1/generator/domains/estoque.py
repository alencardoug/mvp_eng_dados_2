"""Domínio de estoque — 4 tabelas.

A parte mais delicada da geração. `inventory_movements` é livro de eventos:
não se sorteia um movimento, **monta-se** a partir do que já aconteceu — o
recebimento que entrou, a remessa que saiu, a devolução que voltou. Depois o
livro é percorrido em ordem de acontecimento, e só então o saldo existe.

Duas coisas que essa ordem garante e que sorteio nenhum garantiria:

* o saldo **nunca fica negativo** — o par que teria saída sem lastro abre o
  período com o estoque que a demanda dele pede, e não com um ajuste de entrada
  inventado no minuto anterior à saída;
* `aggregate_version` é sequencial e sem lacuna dentro de cada par armazém/SKU,
  que é o que a `UNIQUE (warehouse_id, product_variant_id, aggregate_version)`
  do modelo exige e o que o consumidor do streaming vai usar para ordenar.
"""

from __future__ import annotations

import datetime as dt
import math
from decimal import Decimal

from mvp_ed1.generator.dataset import Dataset
from mvp_ed1.generator.domains.logistica import DESPACHADAS
from mvp_ed1.generator.engine import Motor

_MOTIVOS_DE_AJUSTE = (
    "Inventário cíclico", "Avaria em armazém", "Divergência de conferência",
    "Perda por validade", "Correção de lançamento",
)

#: A carga inicial de estoque do par: uma só, no começo do período.
_ABERTURA = "ESTOQUE-INICIAL"
_METADADOS_DA_ABERTURA = {"motivo": "Carga inicial de estoque", "origem": "abertura"}


def armazens(motor: Motor, dados: Dataset) -> None:
    n = motor.linhas("warehouses")
    dados.guardar("warehouses", motor.preencher("warehouses", [{} for _ in range(n)]))


def livro(motor: Motor, dados: Dataset) -> None:
    """Livro de eventos, reservas e saldo — nesta ordem, que não é arbitrária.

    O saldo é projeção do livro (Modelo de Dados §2.10) e a reserva ocupa parte
    dele; inverter a ordem obrigaria a inventar um saldo e depois torcer para o
    livro bater com ele.
    """
    movimentos = _montar(motor, dados)
    movimentos = _ordenar_e_versionar(motor, dados, movimentos)
    dados.guardar("inventory_movements", motor.preencher("inventory_movements", movimentos))
    reservas = _reservas(motor, dados, movimentos)
    _saldos(motor, dados, movimentos, reservas)


# ── Montagem ─────────────────────────────────────────────────────────────────
def _montar(motor: Motor, dados: Dataset) -> list[dict]:
    fonte = motor.fonte("inventory_movements")
    processo = motor.config.tabelas["inventory_movements"].processo
    alvo = motor.linhas("inventory_movements")
    armazens_ids = [linha["id"] for linha in dados["warehouses"]]
    variantes = dados["product_variants"]

    movimentos: list[dict] = []
    movimentos += _estoque_inicial(motor, fonte, processo, armazens_ids, variantes, demanda_por_par(dados))
    movimentos += _entradas_de_compra(motor, dados)
    movimentos += _saidas_de_venda(motor, dados)
    movimentos += _devolucoes_de_cliente(motor, dados)
    # `max(…, 1)` e `max(…, 2)`: em fator pequeno o arredondamento zeraria a
    # transferência e o ajuste, e com eles sumiriam quatro dos oito tipos de
    # movimento que o modelo aceita. O piso do ADR-0014 vale aqui também.
    movimentos += _devolucoes_a_fornecedor(
        motor, fonte, dados, max(round(alvo * processo["devolucao_a_fornecedor"]), 1)
    )
    movimentos += _transferencias(
        motor, fonte, armazens_ids, variantes, max(round(alvo * processo["transferencias"]) // 2, 1)
    )
    movimentos += _ajustes(
        motor, fonte, armazens_ids, variantes, max(round(alvo * processo["ajustes"]), 2)
    )
    return movimentos


def _evento(
    tipo: str,
    origem: str,
    origem_id: str,
    armazem: int,
    variante: int,
    delta: int,
    momento: dt.datetime,
    *,
    custo: Decimal | None = None,
    correlacao=None,
    causacao=None,
    metadados: dict | None = None,
) -> dict:
    return {
        "movement_type": tipo,
        "source_type": origem,
        "source_id": origem_id,
        "warehouse_id": armazem,
        "product_variant_id": variante,
        "quantity_delta": delta,
        "unit_cost": custo,
        "occurred_at": momento,
        "correlation_id": correlacao,
        "causation_id": causacao,
        "metadata": metadados,
    }


def demanda_por_par(dados: Dataset) -> dict[tuple[int, int], list[tuple[dt.datetime, int]]]:
    """A venda de cada par armazém × SKU: o instante e a quantidade de cada saída por venda.

    São as mesmas saídas que `_saidas_de_venda` põe no livro — a remessa despachada, no armazém dela —,
    e é por elas que a compra e a abertura se dimensionam (V5).
    """
    demanda: dict[tuple[int, int], list[tuple[dt.datetime, int]]] = {}
    for item in dados["shipment_items"]:
        if item["__remessa"]["status"] in DESPACHADAS:
            demanda.setdefault((item["__warehouse_id"], item["__product_variant_id"]), []).append(
                (item["created_at"], item["quantity"]))
    return demanda


def _estoque_inicial(motor, fonte, processo, armazens_ids, variantes, demanda) -> list[dict]:
    """Formação do estoque inicial — Geração de Dados §3, passo 4.

    Sem ele o saldo cobriria só os pares que passaram por recebimento de
    compra, e a cobertura de `inventory_balances` ficaria na metade da
    proporção declarada: 1.520 itens recebidos não estocam 2.500 pares.

    A quantidade é a venda do par nos primeiros `cobertura_da_abertura_dias` do período, e uma unidade
    no par sem venda nesse intervalo (V5; Q73). Até 17/11/2026 era um sorteio de 10 a 400.
    """
    pares = [(a, v["id"], v) for a in armazens_ids for v in variantes]
    quantos = round(len(pares) * processo["cobertura_de_saldo"])
    escolhidos = sorted(fonte.amostra(range(len(pares)), quantos))
    ate = motor.inicio + dt.timedelta(days=processo["cobertura_da_abertura_dias"])

    def abertura(armazem: int, sku: int) -> int:
        return max(1, sum(q for quando, q in demanda.get((armazem, sku), ()) if motor.inicio <= quando <= ate))

    return [
        _evento(
            "adjustment_in", "adjustment", _ABERTURA,
            pares[i][0], pares[i][1], abertura(pares[i][0], pares[i][1]), motor.inicio,
            custo=pares[i][2]["__custo"],
            metadados=dict(_METADADOS_DA_ABERTURA),
        )
        for i in escolhidos
    ]


def _entradas_de_compra(motor: Motor, dados: Dataset) -> list[dict]:
    """Uma entrada por item recebido — e só de recebimento concluído.

    Recebimento `pending` ou `rejected` não move estoque: é essa distinção que
    faz o estado da ordem de compra ter consequência física.
    """
    numeros = {linha["id"]: linha["receipt_number"] for linha in dados["goods_receipts"]}
    return [
        _evento(
            "purchase_receipt", "purchase", numeros[item["goods_receipt_id"]],
            item["__warehouse_id"], item["__product_variant_id"],
            item["quantity_received"], item["created_at"], custo=item["unit_cost"],
        )
        for item in dados["goods_receipt_items"]
        if item["__status"] == "completed" and item["quantity_received"] > 0
    ]


def _saidas_de_venda(motor: Motor, dados: Dataset) -> list[dict]:
    custos = {linha["id"]: linha["__custo"] for linha in dados["product_variants"]}
    return [
        _evento(
            "sale_dispatch", "sale", item["__remessa"]["shipment_code"],
            item["__warehouse_id"], item["__product_variant_id"],
            -item["quantity"], item["created_at"],
            custo=custos[item["__product_variant_id"]],
        )
        for item in dados["shipment_items"]
        if item["__remessa"]["status"] in DESPACHADAS
    ]


def _devolucoes_de_cliente(motor: Motor, dados: Dataset) -> list[dict]:
    custos = {linha["id"]: linha["__custo"] for linha in dados["product_variants"]}
    movimentos = []
    for item in dados["shipment_items"]:
        remessa = item["__remessa"]
        if remessa["status"] != "returned":
            continue
        momento = remessa["delivered_at"] or remessa["created_at"]
        movimentos.append(
            _evento(
                "customer_return", "return", remessa["shipment_code"],
                item["__warehouse_id"], item["__product_variant_id"],
                item["quantity"], min(momento + dt.timedelta(days=3), motor.fim),
                custo=custos[item["__product_variant_id"]],
            )
        )
    return movimentos


def _devolucoes_a_fornecedor(motor, fonte, dados: Dataset, quantos: int) -> list[dict]:
    recebidos = [i for i in dados["goods_receipt_items"] if i["__status"] == "completed"]
    if not recebidos or quantos <= 0:
        return []
    numeros = {linha["id"]: linha["receipt_number"] for linha in dados["goods_receipts"]}
    movimentos = []
    for item in fonte.amostra(recebidos, quantos):
        quantidade = max(1, item["quantity_received"] // 20)
        movimentos.append(
            _evento(
                "supplier_return", "return", numeros[item["goods_receipt_id"]],
                item["__warehouse_id"], item["__product_variant_id"],
                -quantidade,
                motor.relogio.depois(item["created_at"], fonte, 24, 720),
                custo=item["unit_cost"],
            )
        )
    return movimentos


def _transferencias(motor, fonte, armazens_ids, variantes, pares: int) -> list[dict]:
    """Saída e entrada com o mesmo `correlation_id` e a mesma quantidade.

    Transferência que não fecha dos dois lados some do saldo consolidado sem
    deixar rastro — é o caso que a Etapa 7 vai testar nos dois armazéns.
    """
    if len(armazens_ids) < 2 or pares <= 0:
        return []
    movimentos: list[dict] = []
    for _ in range(pares):
        origem, destino = fonte.amostra(armazens_ids, 2)
        variante = fonte.escolha(variantes)
        quantidade = fonte.inteiro(1, 40)
        momento = motor.relogio.sazonal(fonte)
        correlacao = fonte.uuid()
        codigo = f"TRF-{str(correlacao)[:8].upper()}"
        movimentos.append(
            _evento("transfer_out", "transfer", codigo, origem, variante["id"],
                    -quantidade, momento, custo=variante["__custo"], correlacao=correlacao)
        )
        movimentos.append(
            _evento("transfer_in", "transfer", codigo, destino, variante["id"],
                    quantidade, min(momento + dt.timedelta(days=2), motor.fim),
                    custo=variante["__custo"], correlacao=correlacao)
        )
    return movimentos


def _ajustes(motor, fonte, armazens_ids, variantes, quantos: int) -> list[dict]:
    movimentos = []
    for indice in range(max(quantos, 0)):
        entrada = indice % 2 == 0
        variante = fonte.escolha(variantes)
        quantidade = fonte.inteiro(1, 30)
        movimentos.append(
            _evento(
                "adjustment_in" if entrada else "adjustment_out",
                "adjustment",
                f"AJU-{indice + 1:06d}",
                fonte.escolha(armazens_ids),
                variante["id"],
                quantidade if entrada else -quantidade,
                motor.relogio.sazonal(fonte),
                custo=variante["__custo"],
                # O modelo pede motivo documentado no ajuste; é também o que dá
                # ao `metadata` jsonb conteúdo real para o CDC transportar.
                metadados={"motivo": fonte.escolha(_MOTIVOS_DE_AJUSTE)},
            )
        )
    return movimentos


# ── Ordenação, lastro e versionamento ───────────────────────────────────────
def _ordenar_e_versionar(motor: Motor, dados: Dataset, movimentos: list[dict]) -> list[dict]:
    fonte = motor.fonte("inventory_movements")
    processo = motor.config.tabelas["inventory_movements"].processo
    atraso_min, atraso_max = processo["atraso_de_registro_segundos"]
    custos = {linha["id"]: linha["__custo"] for linha in dados["product_variants"]}

    por_agregado: dict[tuple[int, int], list[dict]] = {}
    for movimento in movimentos:
        chave = (movimento["warehouse_id"], movimento["product_variant_id"])
        por_agregado.setdefault(chave, []).append(movimento)

    final: list[dict] = []
    for chave in sorted(por_agregado):
        eventos = sorted(por_agregado[chave], key=lambda m: m["occurred_at"])
        _dar_lastro(motor, chave, eventos, custos[chave[1]], processo["folga_da_abertura"])

        saldo = 0
        for versao, evento in enumerate(eventos, start=1):
            saldo += evento["quantity_delta"]
            if saldo < 0:
                raise ValueError(f"estoque: saldo negativo no par {chave}, versão {versao}")
            evento["aggregate_version"] = versao
            evento["movement_id"] = fonte.uuid()
            evento["causation_id"] = fonte.uuid()
            evento["recorded_at"] = evento["occurred_at"] + dt.timedelta(
                seconds=fonte.inteiro(atraso_min, atraso_max)
            )
            evento["idempotency_key"] = (
                f"{evento['source_type']}:{evento['source_id']}:"
                f"{chave[0]}:{chave[1]}:{versao}"
            )[:100]
            final.append(evento)
    return final


def _dar_lastro(
    motor: Motor, chave: tuple[int, int], eventos: list[dict], custo: Decimal, folga: float
) -> None:
    """Abertura dimensionada pela demanda — invariante 20 do Modelo de Dados §4.

    A venda escolhe o armazém sem olhar o estoque, e três em cada dez pares não
    têm carga inicial: sem isto, a saída encontraria o par vazio. O que faltaria
    ao longo do período entra na abertura dele, com a folga declarada; o par que
    não tinha abertura ganha uma. Não há mais ajuste de entrada criado para
    cobrir a saída no minuto anterior, que fazia o estoque aparecer do nada e
    deixava o giro do trimestre indefinido.
    """
    saldo = falta = 0
    for evento in eventos:
        saldo += evento["quantity_delta"]
        falta = max(falta, -saldo)
    if not falta:
        return
    reforco = math.ceil(falta * (1 + folga))
    abertura = next((e for e in eventos if e["source_id"] == _ABERTURA), None)
    if abertura is not None:
        abertura["quantity_delta"] += reforco
        return
    eventos.insert(
        0,
        _evento(
            "adjustment_in", "adjustment", _ABERTURA, chave[0], chave[1], reforco, motor.inicio,
            custo=custo, metadados=dict(_METADADOS_DA_ABERTURA),
        ),
    )


# ── Reservas e saldo ─────────────────────────────────────────────────────────
def _reservas(motor: Motor, dados: Dataset, movimentos: list[dict]) -> list[dict]:
    """Reserva de um item do carrinho **ou** do pedido a que ela pertence.

    Invariante 18 do Modelo de Dados §4: a reserva é do SKU e da quantidade de
    um item da própria origem, e cada item é reservado no máximo uma vez —
    sortear o par armazém/SKU à parte travava saldo de um produto que o cliente
    nem tinha posto no carrinho. O armazém sai dos que têm movimento daquele
    SKU: reserva onde nunca houve estoque não ocupa saldo nenhum.

    A `CHECK num_nonnulls(cart_id, order_id) = 1` do modelo garante a origem
    única. `origem_carrinho` é intenção: os itens de pedido em aberto são
    poucos, e o que não couber neles vai para os carrinhos, para o total da
    tabela se manter.
    """
    fonte = motor.fonte("stock_reservations")
    processo = motor.config.tabelas["stock_reservations"].processo
    validade = dt.timedelta(hours=processo["validade_horas"])
    armazens_do_sku: dict[int, list[int]] = {}
    for armazem, variante in sorted({(m["warehouse_id"], m["product_variant_id"]) for m in movimentos}):
        armazens_do_sku.setdefault(variante, []).append(armazem)

    itens_do_pedido: dict[int, list[dict]] = {}
    for item in dados["order_items"]:
        itens_do_pedido.setdefault(item["order_id"], []).append(item)
    de_carrinho = [
        (carrinho, item)
        for carrinho in dados["carts"]
        if carrinho["status"] != "converted"
        for item in carrinho.get("__itens", [])
        if item["product_variant_id"] in armazens_do_sku
    ]
    de_pedido = [
        (pedido, item)
        for pedido in dados["orders"]
        if pedido["status"] in ("pending", "paid", "picking")
        for item in itens_do_pedido.get(pedido["id"], [])
        if item["product_variant_id"] in armazens_do_sku
    ]
    estados_de_carrinho = {"open": "active", "abandoned": "released", "expired": "expired"}

    total = motor.linhas("stock_reservations")
    pretendidas = sum(fonte.chance(processo["origem_carrinho"]) for _ in range(total))
    quantas_de_pedido = min(total - pretendidas, len(de_pedido))
    quantas_de_carrinho = min(total - quantas_de_pedido, len(de_carrinho))
    # E a volta: o que não coube nos carrinhos vai para os pedidos que sobraram.
    # Sem ela a tabela saía menor que o piso tendo item elegível para reservar.
    quantas_de_pedido = min(total - quantas_de_carrinho, len(de_pedido))
    escolhidas = [("cart", par) for par in fonte.amostra(de_carrinho, quantas_de_carrinho)]
    escolhidas += [("order", par) for par in fonte.amostra(de_pedido, quantas_de_pedido)]
    _cobrir_estados(escolhidas, de_carrinho, de_pedido, estados_de_carrinho)
    fonte.rng.shuffle(escolhidas)

    esqueletos: list[dict] = []
    for tipo, (origem, item) in escolhidas:
        if tipo == "cart":
            criada, estado = origem["created_at"], _estado_da_reserva(tipo, origem, estados_de_carrinho)
        else:
            criada = origem["placed_at"]
            estado = _estado_da_reserva(tipo, origem, estados_de_carrinho)
        esqueletos.append(
            {
                "warehouse_id": fonte.escolha(armazens_do_sku[item["product_variant_id"]]),
                "product_variant_id": item["product_variant_id"],
                "cart_id": origem["id"] if tipo == "cart" else None,
                "order_id": origem["id"] if tipo == "order" else None,
                "quantity": item["quantity"],
                "status": estado,
                "expires_at": criada + validade,
                "released_at": None if estado == "active" else min(criada + validade, motor.fim),
                "created_at": criada,
                "deleted_at": None,
            }
        )
    return dados.guardar("stock_reservations", motor.preencher("stock_reservations", esqueletos))


def _estado_da_reserva(tipo: str, origem: dict, estados_de_carrinho: dict[str, str]) -> str:
    """O estado que a reserva herda da origem dela: do carrinho, ou do pedido em aberto."""
    if tipo == "cart":
        return estados_de_carrinho[origem["status"]]
    return "consumed" if origem["status"] != "pending" else "active"


def _cobrir_estados(escolhidas, de_carrinho, de_pedido, estados_de_carrinho) -> None:
    """Todo estado de reserva que algum item elegível produz aparece na amostra.

    O estado vem da origem, e a amostra simples o deixa ao acaso: no piso de
    quatro reservas, `expired` sumia na maioria das sementes. O estado que
    falta entra com um item ainda não reservado — nunca o mesmo item duas
    vezes, que a invariante 18 proíbe —, no lugar de um do estado que sobra.
    """
    def estado(par):
        return _estado_da_reserva(par[0], par[1][0], estados_de_carrinho)

    disponiveis = [("cart", par) for par in de_carrinho] + [("order", par) for par in de_pedido]
    usados = {id(par[1][1]) for par in escolhidas}
    for alvo in ("active", "released", "expired", "consumed"):
        presentes = [estado(par) for par in escolhidas]
        if alvo in presentes:
            continue
        candidato = next(
            (par for par in disponiveis if estado(par) == alvo and id(par[1][1]) not in usados), None
        )
        if candidato is None:
            continue
        sobra = max(sorted(set(presentes)), key=presentes.count, default=None)
        if sobra is None or presentes.count(sobra) < 2:
            continue
        posicao = presentes.index(sobra)
        usados.discard(id(escolhidas[posicao][1][1]))
        usados.add(id(candidato[1][1]))
        escolhidas[posicao] = candidato


def _saldos(motor: Motor, dados: Dataset, movimentos: list[dict], reservas: list[dict]) -> None:
    """Projeção do livro: soma dos deltas, e a reserva ativa em cima dela."""
    saldo: dict[tuple[int, int], int] = {}
    ultimo: dict[tuple[int, int], dt.datetime] = {}
    for movimento in movimentos:
        chave = (movimento["warehouse_id"], movimento["product_variant_id"])
        saldo[chave] = saldo.get(chave, 0) + movimento["quantity_delta"]
        anterior = ultimo.get(chave)
        if anterior is None or movimento["occurred_at"] > anterior:
            ultimo[chave] = movimento["occurred_at"]

    reservado: dict[tuple[int, int], int] = {}
    for reserva in reservas:
        if reserva["status"] != "active":
            continue  # Invariante 8: liberada, expirada ou consumida não ocupa saldo.
        chave = (reserva["warehouse_id"], reserva["product_variant_id"])
        reservado[chave] = reservado.get(chave, 0) + reserva["quantity"]

    esqueletos = [
        {
            "warehouse_id": armazem,
            "product_variant_id": variante,
            "quantity_on_hand": quantidade,
            # `CHECK reserva_limitada_ao_saldo`: não se reserva o que não há.
            "quantity_reserved": min(reservado.get((armazem, variante), 0), quantidade),
            "last_movement_at": ultimo[(armazem, variante)],
            "created_at": motor.inicio,
            "deleted_at": None,
        }
        for (armazem, variante), quantidade in sorted(saldo.items())
    ]
    dados.guardar("inventory_balances", motor.preencher("inventory_balances", esqueletos))
